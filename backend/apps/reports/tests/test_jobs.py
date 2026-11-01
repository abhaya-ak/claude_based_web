import datetime
import uuid

import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from moto import mock_aws

from apps.core import aws
from apps.reports.jobs import MAX_ORPHAN_DELETES_PER_RUN, clean_orphan_evidence
from apps.reports.models import (
    Platform,
    ReportEvidence,
    ScamCategory,
    ScamReport,
)


@pytest.fixture
def s3_evidence_bucket():
    with mock_aws():
        aws.reset_clients()
        s3 = aws.client("s3")
        s3.create_bucket(
            Bucket=settings.EVIDENCE_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        yield s3


@pytest.mark.django_db
class TestOrphanEvidenceCleanupJob:
    def test_clean_orphan_evidence_removes_old_unreferenced_keys(
        self, s3_evidence_bucket, monkeypatch
    ):
        s3 = s3_evidence_bucket
        bucket = settings.EVIDENCE_BUCKET

        orphan_key = f"evidence/{uuid.uuid4()}/orphan.png"
        s3.put_object(Bucket=bucket, Key=orphan_key, Body=b"image-data")

        # Advance time by 25 hours
        future = timezone.now() + datetime.timedelta(hours=25)
        monkeypatch.setattr(timezone, "now", lambda: future)

        res = clean_orphan_evidence()
        assert res["deleted_count"] == 1
        assert res["scanned_count"] >= 1

        # Assert key is deleted in S3
        with pytest.raises(ClientError) as exc:
            s3.head_object(Bucket=bucket, Key=orphan_key)
        assert exc.value.response["Error"]["Code"] == "404"

    def test_recent_keys_are_preserved(self, s3_evidence_bucket, monkeypatch):
        s3 = s3_evidence_bucket
        bucket = settings.EVIDENCE_BUCKET

        recent_key = f"evidence/{uuid.uuid4()}/recent.png"
        s3.put_object(Bucket=bucket, Key=recent_key, Body=b"image-data")

        # Advance time by only 10 hours (< 24h)
        future = timezone.now() + datetime.timedelta(hours=10)
        monkeypatch.setattr(timezone, "now", lambda: future)

        res = clean_orphan_evidence()
        assert res["deleted_count"] == 0

        # Assert key is preserved
        head = s3.head_object(Bucket=bucket, Key=recent_key)
        assert head["ContentLength"] == len(b"image-data")

    def test_referenced_keys_are_preserved_even_if_older_than_24h(
        self, s3_evidence_bucket, monkeypatch
    ):
        s3 = s3_evidence_bucket
        bucket = settings.EVIDENCE_BUCKET

        referenced_key = f"evidence/{uuid.uuid4()}/referenced.png"
        s3.put_object(Bucket=bucket, Key=referenced_key, Body=b"image-data")

        # Create report and evidence in DB
        rep = ScamReport.objects.create(
            category=ScamCategory.PHISHING,
            platform=Platform.EMAIL,
            message_text="Phishing with referenced evidence",
            country_code="MY",
            currency="MYR",
            reference_code=f"SCM-{uuid.uuid4().hex[:12].upper()}",
            access_key_hash="fakehash",
        )
        ReportEvidence.objects.create(
            report=rep,
            s3_key=referenced_key,
            sha256="fake_sha256",
            size_bytes=10,
            content_type="image/png",
        )

        # Advance time by 30 hours
        future = timezone.now() + datetime.timedelta(hours=30)
        monkeypatch.setattr(timezone, "now", lambda: future)

        res = clean_orphan_evidence()
        assert res["deleted_count"] == 0

        # Assert key still exists in S3
        head = s3.head_object(Bucket=bucket, Key=referenced_key)
        assert head["ContentLength"] == len(b"image-data")

    def test_foreign_prefixes_are_never_deleted(
        self, s3_evidence_bucket, monkeypatch
    ):
        s3 = s3_evidence_bucket
        bucket = settings.EVIDENCE_BUCKET

        export_key = "exports/audit_dump.csv"
        guide_key = "guides/security_guide.pdf"
        s3.put_object(Bucket=bucket, Key=export_key, Body=b"col1,col2")
        s3.put_object(Bucket=bucket, Key=guide_key, Body=b"%PDF-sample")

        # Advance time by 48 hours
        future = timezone.now() + datetime.timedelta(hours=48)
        monkeypatch.setattr(timezone, "now", lambda: future)

        res = clean_orphan_evidence()
        assert res["deleted_count"] == 0

        # Both foreign objects must still exist
        assert s3.head_object(Bucket=bucket, Key=export_key)["ContentLength"] > 0
        assert s3.head_object(Bucket=bucket, Key=guide_key)["ContentLength"] > 0

    def test_max_500_cap_per_run(self, s3_evidence_bucket, monkeypatch):
        s3 = s3_evidence_bucket
        bucket = settings.EVIDENCE_BUCKET

        total_keys = MAX_ORPHAN_DELETES_PER_RUN + 5
        for i in range(total_keys):
            key = f"evidence/test-bulk/orphan_{i:04d}.png"
            s3.put_object(Bucket=bucket, Key=key, Body=b"x")

        # Advance time by 30 hours
        future = timezone.now() + datetime.timedelta(hours=30)
        monkeypatch.setattr(timezone, "now", lambda: future)

        res = clean_orphan_evidence()
        assert res["deleted_count"] == MAX_ORPHAN_DELETES_PER_RUN

        # 5 keys should remain
        remaining = s3.list_objects_v2(Bucket=bucket, Prefix="evidence/test-bulk/")
        assert remaining.get("KeyCount") == 5

    def test_run_jobs_invokes_clean_orphan_evidence(
        self, s3_evidence_bucket
    ):
        from io import StringIO

        out = StringIO()
        call_command("run_jobs", "--job", "clean_orphan_evidence", stdout=out)
        output = out.getvalue()
        assert "Job 'clean_orphan_evidence' completed:" in output
