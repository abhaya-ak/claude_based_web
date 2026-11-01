import hashlib
import io
import logging
import uuid
import warnings

from django.conf import settings
from PIL import Image

from apps.core import aws
from apps.reports.constants import MAX_EVIDENCE_FILE_SIZE

logger = logging.getLogger(__name__)

# Maximum pixel count allowed before load (D72)
MAX_PIXEL_COUNT = 10_000_000

# Supported signatures (D58)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
PDF_SIGNATURE = b"%PDF-"


class EvidenceValidationError(Exception):
    """Raised when an uploaded evidence file fails validation."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def sniff_content_type(data: bytes) -> tuple[str, str]:
    """
    Sniffs content type and file extension strictly from magic bytes (D58).
    Never trusts client-provided Content-Type or file extension.
    Returns (content_type, extension).
    """
    if data.startswith(PNG_SIGNATURE):
        return "image/png", ".png"
    if data.startswith(JPEG_SIGNATURE):
        return "image/jpeg", ".jpg"
    if data.startswith(PDF_SIGNATURE):
        return "application/pdf", ".pdf"
    raise EvidenceValidationError(
        "invalid_file_type",
        "Only PNG, JPEG, and PDF files are accepted.",
    )


def process_image(data: bytes, expected_content_type: str) -> bytes:
    """
    Validates and re-encodes image using Pillow per D58 and D72:
    - Verifies width * height <= 10,000,000 BEFORE load
    - Treats DecompressionBombWarning and DecompressionBombError as errors
    - Rejects multi-frame / animated images
    - Strips all EXIF, GPS, and metadata
    - Re-encodes in the same format
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            bio = io.BytesIO(data)
            with Image.open(bio) as im:
                # D72: check pixel count before load
                width, height = im.size
                if width * height > MAX_PIXEL_COUNT:
                    raise EvidenceValidationError(
                        "decompression_bomb",
                        f"Image resolution exceeds the limit of {MAX_PIXEL_COUNT} pixels.",
                    )

                # D72: reject animated or multi-frame images
                if getattr(im, "is_animated", False) or getattr(im, "n_frames", 1) > 1:
                    raise EvidenceValidationError(
                        "animated_image_rejected",
                        "Animated or multi-frame images are not permitted.",
                    )

                # Verify Pillow format matches sniffed type
                expected_format = "PNG" if expected_content_type == "image/png" else "JPEG"
                if im.format != expected_format:
                    raise EvidenceValidationError(
                        "invalid_file_type",
                        f"File header mismatch: expected {expected_format}, found {im.format}.",
                    )

                out_bio = io.BytesIO()
                if expected_content_type == "image/jpeg":
                    rgb_im = im.convert("RGB")
                    # Re-encode stripping all metadata/EXIF
                    rgb_im.save(out_bio, format="JPEG", quality=85, optimize=True)
                else:
                    # PNG: reconstruct clean image without metadata chunks
                    clean_im = Image.new(im.mode, im.size)
                    clean_im.putdata(list(im.getdata()))
                    clean_im.save(out_bio, format="PNG", optimize=True)

                return out_bio.getvalue()
        except Image.DecompressionBombError as exc:
            raise EvidenceValidationError(
                "decompression_bomb",
                "Image decompression bomb detected.",
            ) from exc
        except Exception as exc:
            if isinstance(exc, EvidenceValidationError):
                raise
            raise EvidenceValidationError(
                "corrupt_image",
                f"Invalid or corrupted image: {exc}",
            ) from exc


def process_pdf(data: bytes) -> bytes:
    """
    Validates PDF per D58:
    - Signature %PDF- check
    - Size check
    - PDFs stored unmodified
    """
    if not data.startswith(PDF_SIGNATURE):
        raise EvidenceValidationError("invalid_file_type", "Invalid PDF file header.")
    if len(data) > MAX_EVIDENCE_FILE_SIZE:
        raise EvidenceValidationError(
            "file_too_large",
            f"File exceeds maximum allowed size of {MAX_EVIDENCE_FILE_SIZE} bytes.",
        )
    return data


def validate_and_process_evidence_file(file_data: bytes) -> tuple[bytes, str, str, str]:
    """
    Validates file size, sniffs magic bytes, sanitizes image or validates PDF,
    and calculates SHA-256 hash.
    Returns: (clean_bytes, content_type, extension, sha256_hex)
    """
    if not file_data:
        raise EvidenceValidationError("empty_file", "Uploaded file is empty.")

    if len(file_data) > MAX_EVIDENCE_FILE_SIZE:
        raise EvidenceValidationError(
            "file_too_large",
            f"File exceeds maximum allowed size of {MAX_EVIDENCE_FILE_SIZE} bytes.",
        )

    content_type, ext = sniff_content_type(file_data)

    if content_type in ("image/png", "image/jpeg"):
        clean_bytes = process_image(file_data, content_type)
    elif content_type == "application/pdf":
        clean_bytes = process_pdf(file_data)
    else:
        raise EvidenceValidationError("invalid_file_type", "Unsupported file type.")

    sha256_hex = hashlib.sha256(clean_bytes).hexdigest()
    return clean_bytes, content_type, ext, sha256_hex


def upload_evidence(
    report_id: uuid.UUID,
    file_bytes: bytes,
    content_type: str,
    ext: str,
) -> tuple[str, str, int]:
    """
    Uploads processed evidence to S3 per D58, D60, D73:
    - Key: evidence/{report_id}/{uuid4}{ext}
    - ServerSideEncryption: AES256
    - CacheControl: no-store
    - ContentType: sniffed content type
    Returns (s3_key, sha256_hex, size_bytes).
    """
    evidence_id = uuid.uuid4()
    key = f"evidence/{report_id}/{evidence_id}{ext}"
    sha256_hex = hashlib.sha256(file_bytes).hexdigest()
    size_bytes = len(file_bytes)

    s3 = aws.client("s3")
    s3.put_object(
        Bucket=settings.EVIDENCE_BUCKET,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
        ServerSideEncryption="AES256",
        CacheControl="no-store",
    )
    return key, sha256_hex, size_bytes


def delete_evidence_keys(keys: list[str]) -> None:
    """
    Deletes keys from S3 (best-effort rollback on failure) per D59.
    """
    if not keys:
        return
    s3 = aws.client("s3")
    try:
        delete_spec = {"Objects": [{"Key": k} for k in keys]}
        s3.delete_objects(Bucket=settings.EVIDENCE_BUCKET, Delete=delete_spec)
    except Exception as exc:
        logger.warning("Failed to delete S3 evidence keys during rollback: %s", exc)
