import logging
import uuid

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.core import aws
from apps.core.exceptions import StorageUnavailable
from apps.literacy.models import AssetType, EducationalGuide, GuideAsset

logger = logging.getLogger(__name__)

# Size caps per D115
MAX_PDF_SIZE = 10 * 1024 * 1024       # 10 MB
MAX_AUDIO_SIZE = 20 * 1024 * 1024     # 20 MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024      # 5 MB


def sniff_asset_type(data: bytes) -> tuple[str, str, str]:
    """
    Sniffs asset type, MIME content type, and extension from magic bytes.
    Returns (AssetType, content_type, extension).
    Raises ValidationError if unrecognized or unsafe.
    """
    if data.startswith(b"%PDF-"):
        return AssetType.PDF.value, "application/pdf", ".pdf"

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return AssetType.IMAGE.value, "image/png", ".png"

    if data.startswith(b"\xff\xd8\xff"):
        return AssetType.IMAGE.value, "image/jpeg", ".jpg"

    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return AssetType.IMAGE.value, "image/webp", ".webp"

    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return AssetType.AUDIO.value, "audio/mpeg", ".mp3"

    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return AssetType.AUDIO.value, "audio/wav", ".wav"

    if data.startswith(b"OggS"):
        return AssetType.AUDIO.value, "audio/ogg", ".ogg"

    if len(data) >= 12 and data[4:8] == b"ftyp":
        return AssetType.AUDIO.value, "audio/mp4", ".m4a"

    if len(data) >= 2 and data[:2] in (b"\xff\xf1", b"\xff\xf9"):
        return AssetType.AUDIO.value, "audio/aac", ".aac"

    raise ValidationError(
        {"file": ["Invalid file type. Only PDF, Image (PNG, JPEG, WebP), and Audio (MP3, WAV, OGG, MP4, AAC) are accepted."]},
        code="invalid_file_type",
    )


def upload_guide_asset(guide: EducationalGuide, file_obj, data: dict) -> GuideAsset:
    """
    Validates file magic bytes and size caps, uploads to S3 with SSE AES256,
    and creates a GuideAsset database row.
    """
    file_bytes = file_obj.read()
    file_size = len(file_bytes)

    # Magic-byte sniffing
    detected_type, content_type, ext = sniff_asset_type(file_bytes)

    declared_type = data.get("asset_type")
    if declared_type and declared_type != detected_type:
        raise ValidationError(
            {"asset_type": [f"Declared asset_type '{declared_type}' does not match detected file type '{detected_type}'."]},
            code="invalid_file_type",
        )

    # Size caps enforcement per D115
    if detected_type == AssetType.PDF.value and file_size > MAX_PDF_SIZE:
        raise ValidationError(
            {"file": [f"PDF exceeds maximum size of {MAX_PDF_SIZE // (1024 * 1024)} MB."]},
            code="file_too_large",
        )
    if detected_type == AssetType.AUDIO.value and file_size > MAX_AUDIO_SIZE:
        raise ValidationError(
            {"file": [f"Audio exceeds maximum size of {MAX_AUDIO_SIZE // (1024 * 1024)} MB."]},
            code="file_too_large",
        )
    if detected_type == AssetType.IMAGE.value and file_size > MAX_IMAGE_SIZE:
        raise ValidationError(
            {"file": [f"Image exceeds maximum size of {MAX_IMAGE_SIZE // (1024 * 1024)} MB."]},
            code="file_too_large",
        )

    # Validation of fields per database constraints
    alt_text = (data.get("alt_text") or "").strip()
    if detected_type == AssetType.IMAGE.value and not alt_text:
        raise ValidationError(
            {"alt_text": ["Alt text is required for image assets."]},
            code="validation_error",
        )

    duration_seconds = data.get("duration_seconds")
    if duration_seconds is not None and duration_seconds != "":
        try:
            duration_seconds = int(duration_seconds)
            if duration_seconds <= 0:
                raise ValidationError(
                    {"duration_seconds": ["Duration must be a positive integer."]},
                    code="validation_error",
                )
        except (ValueError, TypeError) as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(
                {"duration_seconds": ["Duration must be a valid integer."]},
                code="validation_error",
            ) from exc
    else:
        duration_seconds = None

    sort_order = data.get("sort_order", 0)
    try:
        sort_order = int(sort_order)
    except (ValueError, TypeError):
        sort_order = 0

    # S3 Upload
    s3_key = f"guides/{guide.id}/{uuid.uuid4()}{ext}"
    bucket = getattr(settings, "MEDIA_BUCKET", "scamshield-media-dev")
    s3 = aws.client("s3")
    try:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
    except Exception as exc:
        logger.warning("Guide asset upload to S3 failed: %s", exc)
        raise StorageUnavailable("Storage service temporarily unavailable.") from exc

    asset = GuideAsset.objects.create(
        guide=guide,
        asset_type=detected_type,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=file_size,
        duration_seconds=duration_seconds,
        alt_text=alt_text,
        transcript=data.get("transcript") or "",
        sort_order=sort_order,
    )
    return asset


def delete_guide_asset(asset: GuideAsset) -> None:
    """Deletes the asset database record and its backing S3 object."""
    bucket = getattr(settings, "MEDIA_BUCKET", "scamshield-media-dev")
    s3 = aws.client("s3")
    try:
        s3.delete_object(Bucket=bucket, Key=asset.s3_key)
    except Exception as exc:
        logger.warning("Failed to delete S3 object %s: %s", asset.s3_key, exc)
    asset.delete()
