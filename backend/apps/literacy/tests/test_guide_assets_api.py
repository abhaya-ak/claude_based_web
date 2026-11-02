import io

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.aws import reset_clients
from apps.core.enums import AudienceGroup
from apps.literacy.models import AssetType, ContentStatus, EducationalGuide, GuideAsset, Tactic


@pytest.fixture
def educator_a(db):
    return User.objects.create_user(
        email="educator_asset_a@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def educator_b(db):
    return User.objects.create_user(
        email="educator_asset_b@scamshield.test",
        password="ValidPassword123!",
        role=Role.EDUCATOR,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin_asset@scamshield.test",
        password="ValidPassword123!",
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def guide_a(educator_a):
    return EducationalGuide.objects.create(
        slug="asset-test-guide-a",
        title="Asset Test Guide A",
        summary="A summary for guide A",
        body="Body of guide A",
        audience_groups=[AudienceGroup.GENERAL.value],
        tactics=[Tactic.URGENCY.value],
        status=ContentStatus.DRAFT.value,
        author=educator_a,
    )


@pytest.fixture
def s3_bucket():
    with mock_aws():
        reset_clients()
        s3 = boto3.client("s3", region_name="ap-southeast-1")
        s3.create_bucket(
            Bucket="scamshield-media-test",
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        yield s3
        reset_clients()


# Minimal valid magic bytes payloads
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
VALID_MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x44" + b"\x00" * 100


@pytest.mark.django_db
class TestGuideAssetVaultAPI:
    def test_educator_uploads_valid_image_asset_with_alt_text(self, s3_bucket, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        file = io.BytesIO(VALID_PNG_BYTES)
        file.name = "diagram.png"

        data = {
            "file": file,
            "asset_type": AssetType.IMAGE.value,
            "alt_text": "Phishing detection diagram showing URL inspection.",
            "sort_order": 1,
        }
        res = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            data,
            format="multipart",
        )
        assert res.status_code == 201
        assert res.data["asset_type"] == AssetType.IMAGE.value
        assert res.data["alt_text"] == "Phishing detection diagram showing URL inspection."
        assert res.data["content_type"] == "image/png"
        assert res.data["size_bytes"] == len(VALID_PNG_BYTES)
        assert res.data["url"].startswith("/media/guides/")

        # Verify S3 object exists with SSE AES256
        asset_id = res.data["id"]
        asset = GuideAsset.objects.get(id=asset_id)
        obj = s3_bucket.get_object(Bucket="scamshield-media-test", Key=asset.s3_key)
        assert obj["ServerSideEncryption"] == "AES256"
        assert obj["ContentType"] == "image/png"

    def test_educator_uploads_valid_pdf_asset(self, s3_bucket, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        file = io.BytesIO(VALID_PDF_BYTES)
        file.name = "checklist.pdf"

        data = {
            "file": file,
            "asset_type": AssetType.PDF.value,
            "sort_order": 2,
        }
        res = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            data,
            format="multipart",
        )
        assert res.status_code == 201
        assert res.data["asset_type"] == AssetType.PDF.value
        assert res.data["content_type"] == "application/pdf"
        assert res.data["url"].startswith("/media/guides/")

    def test_educator_uploads_valid_audio_asset(self, s3_bucket, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        file = io.BytesIO(VALID_MP3_BYTES)
        file.name = "explanation.mp3"

        data = {
            "file": file,
            "asset_type": AssetType.AUDIO.value,
            "duration_seconds": 65,
            "transcript": "Audio narration explaining how scammers forge caller ID.",
        }
        res = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            data,
            format="multipart",
        )
        assert res.status_code == 201
        assert res.data["asset_type"] == AssetType.AUDIO.value
        assert res.data["duration_seconds"] == 65
        assert res.data["transcript"] == "Audio narration explaining how scammers forge caller ID."
        assert res.data["content_type"] == "audio/mpeg"

    def test_to_be_proven_18_spoofed_file_type_rejected(self, s3_bucket, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        # Spoofed PDF containing HTML / script
        file = io.BytesIO(b"<html><script>alert('xss')</script></html>")
        file.name = "malicious.pdf"

        data = {
            "file": file,
            "asset_type": AssetType.PDF.value,
        }
        res = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            data,
            format="multipart",
        )
        assert res.status_code == 400
        assert res.data["error"]["code"] in ("validation_error", "invalid_file_type")

    def test_to_be_proven_18_size_limits_enforced(self, s3_bucket, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        # 1. Image over 5MB (5 * 1024 * 1024 + 1 bytes)
        oversized_image = io.BytesIO(VALID_PNG_BYTES + b"\x00" * (5 * 1024 * 1024))
        oversized_image.name = "huge.png"
        res_img = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            {"file": oversized_image, "asset_type": AssetType.IMAGE.value, "alt_text": "Huge"},
            format="multipart",
        )
        assert res_img.status_code == 400
        assert res_img.data["error"]["code"] in ("validation_error", "file_too_large")

        # 2. PDF over 10MB
        oversized_pdf = io.BytesIO(VALID_PDF_BYTES + b"\x00" * (10 * 1024 * 1024))
        oversized_pdf.name = "huge.pdf"
        res_pdf = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            {"file": oversized_pdf, "asset_type": AssetType.PDF.value},
            format="multipart",
        )
        assert res_pdf.status_code == 400
        assert res_pdf.data["error"]["code"] in ("validation_error", "file_too_large")

        # 3. Audio over 20MB
        oversized_audio = io.BytesIO(VALID_MP3_BYTES + b"\x00" * (20 * 1024 * 1024))
        oversized_audio.name = "huge.mp3"
        res_aud = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            {"file": oversized_audio, "asset_type": AssetType.AUDIO.value},
            format="multipart",
        )
        assert res_aud.status_code in (400, 413)
        body = res_aud.json() if hasattr(res_aud, "json") else res_aud.data
        assert body["error"]["code"] in ("validation_error", "file_too_large", "payload_too_large")

    def test_image_without_alt_text_rejected(self, s3_bucket, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        file = io.BytesIO(VALID_PNG_BYTES)
        file.name = "chart.png"

        # Missing alt_text for IMAGE
        res = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            {"file": file, "asset_type": AssetType.IMAGE.value, "alt_text": "   "},
            format="multipart",
        )
        assert res.status_code == 400
        assert res.data["error"]["code"] == "validation_error"

    def test_negative_or_zero_duration_rejected(self, s3_bucket, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        file = io.BytesIO(VALID_MP3_BYTES)
        file.name = "audio.mp3"

        res = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            {"file": file, "asset_type": AssetType.AUDIO.value, "duration_seconds": 0},
            format="multipart",
        )
        assert res.status_code == 400
        assert res.data["error"]["code"] == "validation_error"

    def test_educator_cannot_upload_or_delete_asset_on_other_educator_guide(
        self, s3_bucket, educator_a, educator_b, guide_a
    ):
        client = APIClient()
        client.force_authenticate(user=educator_b)

        # Upload attempt -> 403
        file = io.BytesIO(VALID_PNG_BYTES)
        file.name = "unauthorized.png"
        res_post = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            {"file": file, "asset_type": AssetType.IMAGE.value, "alt_text": "Alt"},
            format="multipart",
        )
        assert res_post.status_code == 403

        # Create asset as educator_a
        asset = GuideAsset.objects.create(
            guide=guide_a,
            asset_type=AssetType.IMAGE.value,
            s3_key=f"guides/{guide_a.id}/existing.png",
            content_type="image/png",
            size_bytes=100,
            alt_text="Alt",
        )

        # Delete attempt by educator_b -> 403
        res_del = client.delete(f"/api/v1/studio/guides/{guide_a.id}/assets/{asset.id}/")
        assert res_del.status_code == 403

    def test_delete_asset_removes_db_row_and_s3_object(self, s3_bucket, educator_a, guide_a):
        client = APIClient()
        client.force_authenticate(user=educator_a)

        file = io.BytesIO(VALID_PNG_BYTES)
        file.name = "delete_me.png"
        res = client.post(
            f"/api/v1/studio/guides/{guide_a.id}/assets/",
            {"file": file, "asset_type": AssetType.IMAGE.value, "alt_text": "Delete me"},
            format="multipart",
        )
        assert res.status_code == 201
        asset_id = res.data["id"]
        asset = GuideAsset.objects.get(id=asset_id)
        s3_key = asset.s3_key

        # Confirm S3 object exists
        s3_bucket.head_object(Bucket="scamshield-media-test", Key=s3_key)

        # Delete asset
        res_del = client.delete(f"/api/v1/studio/guides/{guide_a.id}/assets/{asset_id}/")
        assert res_del.status_code == 204
        assert not GuideAsset.objects.filter(id=asset_id).exists()

        # Confirm S3 object is deleted
        with pytest.raises(ClientError):
            s3_bucket.head_object(Bucket="scamshield-media-test", Key=s3_key)
