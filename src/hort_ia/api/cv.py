"""Computer Vision endpoints: image quality filtering and preprocessing for mobile devices."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ..cv import ImagePipeline, ImageProcessingError, ImageQualityAssessment, StandardizedImageInfo

router = APIRouter(prefix="/cv", tags=["computer-vision"])
_pipeline = ImagePipeline()


@router.post(
    "/validate",
    response_model=ImageQualityAssessment,
    summary="Validate image quality from mobile devices",
    description="Inspects sharpness, illumination, contrast and dimensions. "
    "Returns user-friendly feedback in Portuguese for urban growers.",
)
async def validate_image(
    file: Annotated[UploadFile, File(description="Plant leaf image (JPEG, PNG, WebP)")],
) -> ImageQualityAssessment:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="O arquivo enviado não é uma imagem válida (use JPEG, PNG ou WebP).",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de imagem vazio.")

    try:
        assessment, _ = _pipeline.assess_quality(content)
        return assessment
    except ImageProcessingError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.post(
    "/preprocess",
    response_model=StandardizedImageInfo,
    summary="Validate and standardize image for entry-level devices",
    description="Validates quality and resizes image to 224x224 RGB JPEG, removing EXIF metadata (LGPD compliant).",
)
async def preprocess_image(
    file: Annotated[UploadFile, File(description="Plant leaf image (JPEG, PNG, WebP)")],
) -> StandardizedImageInfo:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="O arquivo enviado não é uma imagem válida (use JPEG, PNG ou WebP).",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de imagem vazio.")

    try:
        assessment, info, _, _ = _pipeline.process(content, require_valid=True)
        if not assessment.is_valid:
            reasons = "; ".join(assessment.rejection_reasons)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Imagem rejeitada pelo controle de qualidade: {reasons}. Dica: {assessment.user_feedback}",
            )
        return info
    except ImageProcessingError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
