import io
import numpy as np
import pytest
from PIL import Image
from starlette.testclient import TestClient

from hort_ia.api.main import app
from hort_ia.cv import ImagePipeline, ImageProcessingError, PipelineConfig


def create_sample_image(
    width: int = 300,
    height: int = 300,
    kind: str = "sharp",
) -> bytes:
    """Generate deterministic synthetic images for test cases."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)

    if kind == "sharp":
        # High contrast checkerboard pattern with clear borders
        block = 20
        for y in range(0, height, block):
            for x in range(0, width, block):
                val = 200 if ((x // block) + (y // block)) % 2 == 0 else 50
                arr[y : y + block, x : x + block] = val
    elif kind == "blurry":
        # Smooth gradual sinusoidal gradient (no high frequency edges)
        y_grad = np.sin(np.linspace(0, 3, height))[:, None]
        x_grad = np.cos(np.linspace(0, 3, width))[None, :]
        val = ((y_grad + x_grad + 2) / 4.0 * 120 + 60).astype(np.uint8)
        arr[:, :, 0] = val
        arr[:, :, 1] = val
        arr[:, :, 2] = val
    elif kind == "dark":
        # Entirely underexposed (pixel values 5 to 20)
        arr[:] = 12
    elif kind == "bright":
        # Entirely overexposed (pixel values 240 to 255)
        arr[:] = 245

    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_sharp_valid_image_is_approved_and_standardized():
    pipeline = ImagePipeline()
    valid_bytes = create_sample_image(width=640, height=480, kind="sharp")

    assessment, info, encoded, rgb = pipeline.process(valid_bytes)

    assert assessment.is_valid is True
    assert len(assessment.rejection_reasons) == 0
    assert assessment.blur_score >= pipeline.config.min_blur_score
    assert info is not None
    assert info.width == 224
    assert info.height == 224
    assert info.channels == 3
    assert info.format == "JPEG"
    assert info.size_bytes < 35000  # < 35 KB for mobile connectivity
    assert rgb.shape == (224, 224, 3)


def test_blurry_image_is_rejected():
    pipeline = ImagePipeline()
    blurry_bytes = create_sample_image(width=400, height=400, kind="blurry")

    assessment, info, _, _ = pipeline.process(blurry_bytes, require_valid=True)

    assert assessment.is_valid is False
    assert any("borrada" in r.lower() or "foco" in r.lower() for r in assessment.rejection_reasons)
    assert assessment.user_feedback is not None
    assert "Segure o celular com firmeza" in assessment.user_feedback
    assert info is None


def test_underexposed_dark_image_is_rejected():
    pipeline = ImagePipeline()
    dark_bytes = create_sample_image(width=300, height=300, kind="dark")

    assessment, info, _, _ = pipeline.process(dark_bytes, require_valid=True)

    assert assessment.is_valid is False
    assert any("escura" in r.lower() for r in assessment.rejection_reasons)
    assert "escuro" in assessment.user_feedback.lower()
    assert info is None


def test_overexposed_bright_image_is_rejected():
    pipeline = ImagePipeline()
    bright_bytes = create_sample_image(width=300, height=300, kind="bright")

    assessment, info, _, _ = pipeline.process(bright_bytes, require_valid=True)

    assert assessment.is_valid is False
    assert any("claridade" in r.lower() or "reflexo" in r.lower() for r in assessment.rejection_reasons)
    assert info is None


def test_low_resolution_image_is_rejected():
    pipeline = ImagePipeline()
    tiny_bytes = create_sample_image(width=80, height=80, kind="sharp")

    assessment, info, _, _ = pipeline.process(tiny_bytes, require_valid=True)

    assert assessment.is_valid is False
    assert any("resolução muito baixa" in r.lower() for r in assessment.rejection_reasons)
    assert info is None


def test_corrupted_bytes_raise_image_processing_error():
    pipeline = ImagePipeline()
    with pytest.raises(ImageProcessingError):
        pipeline.assess_quality(b"this is not an image at all")


def test_exif_metadata_is_stripped_for_lgpd():
    """Verify that EXIF tags (such as GPS or camera serials) are stripped during standardization."""
    # Create image with EXIF tag
    raw_img = Image.fromarray(np.full((300, 300, 3), 120, dtype=np.uint8))
    exif = raw_img.getexif()
    exif[0x010E] = "Proprietario da Horta: João da Silva (LGPD test)"  # ImageDescription tag

    buf = io.BytesIO()
    raw_img.save(buf, format="JPEG", exif=exif)
    input_bytes = buf.getvalue()

    pipeline = ImagePipeline()
    assessment, bgr = pipeline.assess_quality(input_bytes)
    info, encoded, _ = pipeline.standardize(bgr, assessment)

    # Decode encoded bytes to verify EXIF is completely gone
    processed_img = Image.open(io.BytesIO(encoded))
    processed_exif = processed_img.getexif()
    assert len(processed_exif) == 0 or 0x010E not in processed_exif
    assert info.exif_stripped is True


# --- API Endpoint Tests ---


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_api_cv_validate_endpoint_success(client: TestClient):
    valid_bytes = create_sample_image(width=400, height=400, kind="sharp")
    response = client.post(
        "/cv/validate",
        files={"file": ("leaf.jpg", valid_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["blur_score"] > 0


def test_api_cv_validate_endpoint_unsupported_media(client: TestClient):
    response = client.post(
        "/cv/validate",
        files={"file": ("text.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415


def test_api_cv_preprocess_endpoint_success(client: TestClient):
    valid_bytes = create_sample_image(width=400, height=400, kind="sharp")
    response = client.post(
        "/cv/preprocess",
        files={"file": ("leaf.jpg", valid_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["width"] == 224
    assert data["height"] == 224
    assert data["channels"] == 3
    assert data["format"] == "JPEG"
    assert data["exif_stripped"] is True


def test_api_cv_preprocess_endpoint_rejects_blurry(client: TestClient):
    blurry_bytes = create_sample_image(width=400, height=400, kind="blurry")
    response = client.post(
        "/cv/preprocess",
        files={"file": ("blurry.jpg", blurry_bytes, "image/jpeg")},
    )
    assert response.status_code == 422
    assert "Imagem rejeitada pelo controle de qualidade" in response.json()["detail"]
