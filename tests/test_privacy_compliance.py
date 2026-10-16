import io
import numpy as np
import pytest
from PIL import Image

from hort_ia.core.privacy import (
    ConsentError,
    ConsentRecord,
    ConsentValidator,
    ImageAnonymizer,
    PIIAuditor,
    PrivacyPipeline,
    TextAnonymizer,
)


# --- 9.1.2-4: Consent Validation Tests ---


def test_valid_consent_is_accepted():
    validator = ConsentValidator(min_terms_version="v1.0")
    consent = ConsentRecord(
        grower_id="grower_123",
        consent_given=True,
        purpose="ai_training_and_inference",
        terms_version="v1.0",
        privacy_policy_version="v1.0",
    )
    is_valid, reasons = validator.validate(consent)
    assert is_valid is True
    assert len(reasons) == 0
    # Should not raise
    validator.assert_valid(consent)


def test_missing_or_false_consent_is_rejected():
    validator = ConsentValidator()
    # None
    assert validator.validate(None)[0] is False
    with pytest.raises(ConsentError):
        validator.assert_valid(None)

    # consent_given = False
    refused = ConsentRecord(
        grower_id="grower_refused",
        consent_given=False,
        purpose="ai_training",
    )
    assert validator.validate(refused)[0] is False


def test_revoked_consent_is_rejected():
    validator = ConsentValidator()
    revoked = ConsentRecord(
        grower_id="grower_revoked",
        consent_given=True,
        purpose="ai_training",
        revoked=True,
    )
    is_valid, reasons = validator.validate(revoked)
    assert is_valid is False
    assert any("revogado" in r for r in reasons)


def test_invalid_purpose_or_outdated_terms_is_rejected():
    validator = ConsentValidator(min_terms_version="v2.0")
    wrong_purpose = ConsentRecord(
        grower_id="grower_456",
        consent_given=True,
        purpose="marketing_newsletter_only",
        terms_version="v2.0",
    )
    assert validator.validate(wrong_purpose)[0] is False

    old_terms = ConsentRecord(
        grower_id="grower_789",
        consent_given=True,
        purpose="ai_training",
        terms_version="v1.0",  # Below required v2.0
    )
    assert validator.validate(old_terms)[0] is False


# --- 9.1.2-5: PII Auditor Tests ---


def test_pii_auditor_identifies_textual_pii():
    auditor = PIIAuditor()
    sample_text = (
        "Relatório de colheita do agricultor João da Silva. "
        "CPF: 123.456.789-00, Telefone (41) 98765-4321, "
        "Email para contato: joao.horta@gmail.com."
    )
    report = auditor.audit_text(sample_text, known_names=["João da Silva"])
    assert report.has_sensitive_data is True
    assert "123.456.789-00" in report.found_cpfs
    assert "joao.horta@gmail.com" in report.found_emails
    assert len(report.found_phones) > 0
    assert "João da Silva" in report.found_grower_names


def test_pii_auditor_identifies_exif_gps():
    raw_img = Image.fromarray(np.full((100, 100, 3), 120, dtype=np.uint8))
    exif = raw_img.getexif()
    # Pillow 12.x: usar get_ifd() para criar o IFD de GPS corretamente
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1] = "N"   # GPSLatitudeRef
    gps_ifd[3] = "W"   # GPSLongitudeRef
    exif[0x0110] = "Smartphone XYZ-2026"  # Camera Model

    buf = io.BytesIO()
    raw_img.save(buf, format="JPEG", exif=exif)

    auditor = PIIAuditor()
    report = auditor.audit_image_metadata(buf.getvalue())
    assert report.found_exif_gps is True
    assert report.found_exif_device_info is True


# --- 9.1.2-6 & 9.1.2-7: Anonymization Implementation Tests ---


def test_text_anonymizer_masks_pii_and_creates_pseudonyms():
    anonymizer = TextAnonymizer(salt="test_salt_123")
    sample_text = "Agricultor Marcos Souza, CPF 987.654.321-99 e fone (11) 91234-5678, email marcos@horta.org"
    name_map = {"Marcos Souza": anonymizer.generate_pseudonym("Marcos Souza")}

    clean = anonymizer.anonymize_text(sample_text, name_map=name_map)

    assert "987.654.321-99" not in clean
    assert "[CPF_REMOVIDO]" in clean
    assert "marcos@horta.org" not in clean
    assert "[EMAIL_REMOVIDO]" in clean
    assert "Marcos Souza" not in clean
    assert "Produtor_" in clean


def test_text_anonymizer_grower_record():
    anonymizer = TextAnonymizer()
    record = {
        "grower_name": "Maria de Oliveira",
        "cpf": "111.222.333-44",
        "phone": "(41) 9999-8888",
        "crop": "alface",
        "harvest_kg": 45.5,
        "notes": "Entrar em contato pelo email maria@organicos.com para dúvidas",
    }
    sanitized = anonymizer.anonymize_grower_record(record)

    assert "grower_name" not in sanitized
    assert "grower_pseudo_id" in sanitized
    assert "cpf" not in sanitized
    assert "phone" not in sanitized
    assert "[EMAIL_REMOVIDO]" in sanitized["notes"]
    assert sanitized["crop"] == "alface"
    assert sanitized["harvest_kg"] == 45.5


def test_image_anonymizer_strips_exif():
    raw_img = Image.fromarray(np.full((120, 120, 3), 100, dtype=np.uint8))
    exif = raw_img.getexif()
    # Pillow 12.x: usar get_ifd() para criar o IFD de GPS corretamente
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1] = "S"   # GPSLatitudeRef
    exif[0x010E] = "Propriedade Privada - Chácara das Flores"

    buf = io.BytesIO()
    raw_img.save(buf, format="JPEG", exif=exif)

    anonymizer = ImageAnonymizer()
    clean_bytes = anonymizer.strip_exif(buf.getvalue())

    # Decode again
    decoded = Image.open(io.BytesIO(clean_bytes))
    assert len(decoded.getexif()) == 0


def test_end_to_end_privacy_pipeline():
    pipeline = PrivacyPipeline()

    raw_img = Image.fromarray(np.full((150, 150, 3), 150, dtype=np.uint8))
    buf = io.BytesIO()
    raw_img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    valid_consent = ConsentRecord(
        grower_id="grower_777",
        consent_given=True,
        purpose="ai_training_and_inference",
    )
    meta = {
        "grower_name": "Carlos Mendes",
        "cpf": "000.111.222-33",
        "notes": "Coleta de folhas com ferrugem",
    }

    result = pipeline.process_submission(img_bytes, valid_consent, meta)

    assert result["status"] == "anonymized_and_compliant"
    assert result["consent_validated"] is True
    assert result["exif_stripped"] is True
    assert len(result["anonymized_image_bytes"]) > 0
    clean_meta = result["anonymized_metadata"]
    assert "grower_pseudo_id" in clean_meta
    assert "cpf" not in clean_meta


def test_privacy_pipeline_rejects_without_consent():
    pipeline = PrivacyPipeline()
    raw_img = Image.fromarray(np.full((100, 100, 3), 100, dtype=np.uint8))
    buf = io.BytesIO()
    raw_img.save(buf, format="JPEG")

    invalid_consent = ConsentRecord(
        grower_id="grower_denied",
        consent_given=False,
        purpose="ai_training",
    )

    with pytest.raises(ConsentError):
        pipeline.process_submission(buf.getvalue(), invalid_consent)
