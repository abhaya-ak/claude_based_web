import io
import uuid
import warnings

import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management import call_command
from moto import mock_aws
from PIL import Image

from apps.core import aws
from apps.reports.evidence import (
    MAX_EVIDENCE_FILE_SIZE,
    EvidenceValidationError,
    delete_evidence_keys,
    process_image,
    process_pdf,
    sniff_content_type,
    upload_evidence,
    validate_and_process_evidence_file,
)


def create_minimal_png() -> bytes:
    bio = io.BytesIO()
    im = Image.new("RGB", (10, 10), color="blue")
    im.save(bio, format="PNG")
    return bio.getvalue()


def create_minimal_jpeg(with_exif: bool = False) -> bytes:
    bio = io.BytesIO()
    im = Image.new("RGB", (10, 10), color="red")
    if with_exif:
        exif = im.getexif()
        # 0x013B is Artist tag
        exif[0x013B] = "Secret Reporter Name"
        # 0x010E is ImageDescription
        exif[0x010E] = "Location: 3.1390, 101.6869"
        im.save(bio, format="JPEG", exif=exif)
    else:
        im.save(bio, format="JPEG")
    return bio.getvalue()


def create_minimal_pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


# ==============================================================================
# Magic Byte Sniffing & Basic Validation
# ==============================================================================


class TestSniffContentType:
    def test_sniff_png(self):
        data = create_minimal_png()
        ctype, ext = sniff_content_type(data)
        assert ctype == "image/png"
        assert ext == ".png"

    def test_sniff_jpeg(self):
        data = create_minimal_jpeg()
        ctype, ext = sniff_content_type(data)
        assert ctype == "image/jpeg"
        assert ext == ".jpg"

    def test_sniff_pdf(self):
        data = create_minimal_pdf()
        ctype, ext = sniff_content_type(data)
        assert ctype == "application/pdf"
        assert ext == ".pdf"

    def test_reject_exe_file(self):
        exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
        with pytest.raises(EvidenceValidationError) as exc:
            sniff_content_type(exe_bytes)
        assert exc.value.code == "invalid_file_type"

    def test_reject_text_disguised_as_pdf(self):
        text_bytes = b"Hello, this is just plain text content without a PDF header."
        with pytest.raises(EvidenceValidationError) as exc:
            sniff_content_type(text_bytes)
        assert exc.value.code == "invalid_file_type"

    def test_reject_polyglot_or_html(self):
        html_bytes = b"<!DOCTYPE html><html><body><script>alert(1)</script></body></html>"
        with pytest.raises(EvidenceValidationError) as exc:
            sniff_content_type(html_bytes)
        assert exc.value.code == "invalid_file_type"


# ==============================================================================
# Image Processing & Security Caps
# ==============================================================================


class TestImageProcessing:
    def test_exif_and_metadata_stripped_from_jpeg(self):
        raw_jpeg = create_minimal_jpeg(with_exif=True)
        # Verify original raw bytes have the metadata
        orig_im = Image.open(io.BytesIO(raw_jpeg))
        assert orig_im.getexif().get(0x013B) == "Secret Reporter Name"

        clean_bytes = process_image(raw_jpeg, "image/jpeg")
        clean_im = Image.open(io.BytesIO(clean_bytes))
        clean_exif = clean_im.getexif()
        assert not clean_exif or 0x013B not in clean_exif
        assert "Secret Reporter Name" not in str(clean_exif)

    def test_clean_png_processed(self):
        raw_png = create_minimal_png()
        clean_bytes = process_image(raw_png, "image/png")
        assert clean_bytes.startswith(b"\x89PNG")
        clean_im = Image.open(io.BytesIO(clean_bytes))
        assert clean_im.size == (10, 10)

    def test_png_pixel_data_preserved_and_metadata_stripped(self):
        # Create non-trivial image with distinct pixels and text metadata
        orig = Image.new("RGBA", (4, 4))
        for x in range(4):
            for y in range(4):
                orig.putpixel((x, y), (x * 40, y * 50, (x + y) * 25, 255))

        bio = io.BytesIO()
        from PIL.PngImagePlugin import PngInfo

        info = PngInfo()
        info.add_text("ReporterNotes", "Confidential user statement")
        orig.save(bio, format="PNG", pnginfo=info)
        raw_png = bio.getvalue()

        # Verify metadata exists on original
        with Image.open(io.BytesIO(raw_png)) as check_orig:
            assert "ReporterNotes" in check_orig.text

        # Re-encode through evidence processor
        clean_bytes = process_image(raw_png, "image/png")
        with Image.open(io.BytesIO(clean_bytes)) as clean_im:
            # Metadata stripped
            assert "ReporterNotes" not in getattr(clean_im, "text", {})
            # Pixel data preserved identically
            assert clean_im.size == orig.size
            assert clean_im.mode == orig.mode
            assert clean_im.tobytes() == orig.tobytes()

    def test_evidence_processing_emits_zero_warnings(self):
        raw_png = create_minimal_png()
        raw_jpeg = create_minimal_jpeg(with_exif=True)
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            process_image(raw_png, "image/png")
            process_image(raw_jpeg, "image/jpeg")

        evidence_warnings = [
            w for w in recorded if "evidence.py" in str(w.filename)
        ]
        assert len(evidence_warnings) == 0

    def test_decompression_bomb_pixel_cap_rejected(self):
        # 10,001 x 1,000 = 10,001,000 pixels > 10,000,000
        bio = io.BytesIO()
        im = Image.new("RGB", (10001, 1000), color="white")
        im.save(bio, format="PNG")
        oversized_data = bio.getvalue()

        with pytest.raises(EvidenceValidationError) as exc:
            process_image(oversized_data, "image/png")
        assert exc.value.code == "decompression_bomb"

    def test_animated_image_rejected(self):
        bio = io.BytesIO()
        im1 = Image.new("RGBA", (10, 10), color="red")
        im2 = Image.new("RGBA", (10, 10), color="blue")
        # Save as multi-frame animated PNG (APNG)
        im1.save(bio, format="PNG", save_all=True, append_images=[im2])
        apng_data = bio.getvalue()

        # Check rejection
        with pytest.raises(EvidenceValidationError) as exc:
            process_image(apng_data, "image/png")
        assert exc.value.code in ("animated_image_rejected", "decompression_bomb")

    def test_corrupt_image_rejected(self):
        corrupt_png = b"\x89PNG\r\n\x1a\n" + b"garbage_random_binary_content" * 20
        with pytest.raises(EvidenceValidationError) as exc:
            process_image(corrupt_png, "image/png")
        assert exc.value.code == "corrupt_image"


# ==============================================================================
# PDF Processing & Size Caps
# ==============================================================================


class TestPDFProcessing:
    def test_valid_pdf_passes_unmodified(self):
        raw_pdf = create_minimal_pdf()
        clean_pdf = process_pdf(raw_pdf)
        assert clean_pdf == raw_pdf

    def test_pdf_too_large_rejected(self):
        header = b"%PDF-1.4\n"
        oversized_pdf = header + b"x" * (MAX_EVIDENCE_FILE_SIZE + 10)
        with pytest.raises(EvidenceValidationError) as exc:
            process_pdf(oversized_pdf)
        assert exc.value.code == "file_too_large"

    def test_empty_file_rejected(self):
        with pytest.raises(EvidenceValidationError) as exc:
            validate_and_process_evidence_file(b"")
        assert exc.value.code == "empty_file"


# ==============================================================================
# S3 Storage & Security Configurations
# ==============================================================================


@mock_aws
class TestS3EvidenceVault:
    def setup_method(self, method=None):
        aws.reset_clients()
        s3 = aws.client("s3")
        s3.create_bucket(
            Bucket=settings.EVIDENCE_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        s3.put_public_access_block(
            Bucket=settings.EVIDENCE_BUCKET,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )

    def test_upload_evidence_stores_with_aes256_and_no_store(self):
        report_id = uuid.uuid4()
        clean_png = create_minimal_png()

        key, sha256_hex, size_bytes = upload_evidence(
            report_id=report_id,
            file_bytes=clean_png,
            content_type="image/png",
            ext=".png",
        )

        assert key.startswith(f"evidence/{report_id}/")
        assert key.endswith(".png")
        assert size_bytes == len(clean_png)
        assert len(sha256_hex) == 64

        s3 = aws.client("s3")
        obj = s3.get_object(Bucket=settings.EVIDENCE_BUCKET, Key=key)
        assert obj["ContentType"] == "image/png"
        assert obj["ServerSideEncryption"] == "AES256"
        assert obj["CacheControl"] == "no-store"
        assert obj["Body"].read() == clean_png

    def test_delete_evidence_keys_removes_objects(self):
        report_id = uuid.uuid4()
        clean_pdf = create_minimal_pdf()
        key, _, _ = upload_evidence(
            report_id=report_id,
            file_bytes=clean_pdf,
            content_type="application/pdf",
            ext=".pdf",
        )

        s3 = aws.client("s3")
        # Ensure it exists
        s3.head_object(Bucket=settings.EVIDENCE_BUCKET, Key=key)

        # Delete it
        delete_evidence_keys([key])

        # Verify it is deleted
        with pytest.raises(ClientError):
            s3.head_object(Bucket=settings.EVIDENCE_BUCKET, Key=key)

    def test_s3_bucket_has_no_public_access_or_policy(self):
        s3 = aws.client("s3")
        pab = s3.get_public_access_block(Bucket=settings.EVIDENCE_BUCKET)
        config = pab["PublicAccessBlockConfiguration"]
        assert config["BlockPublicAcls"] is True
        assert config["IgnorePublicAcls"] is True
        assert config["BlockPublicPolicy"] is True
        assert config["RestrictPublicBuckets"] is True

    def test_ensure_evidence_bucket_command_is_idempotent(self):
        # Call command first time
        call_command("ensure_evidence_bucket")
        s3 = aws.client("s3")
        pab = s3.get_public_access_block(Bucket=settings.EVIDENCE_BUCKET)
        assert pab["PublicAccessBlockConfiguration"]["BlockPublicAcls"] is True

        # Call command second time (idempotency check)
        call_command("ensure_evidence_bucket")
        pab2 = s3.get_public_access_block(Bucket=settings.EVIDENCE_BUCKET)
        assert pab2["PublicAccessBlockConfiguration"]["BlockPublicPolicy"] is True
