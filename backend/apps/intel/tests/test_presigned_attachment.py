from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.services.evidence_service import issue_evidence_presigned_urls
from apps.reports.models import Platform, ReportEvidence, ReportStatus, ScamCategory, ScamReport


@pytest.mark.django_db
class TestPresignedAttachment:
    """
    D73 / Phase 12 verification:
    Evidence presigned URL must set ResponseContentDisposition='attachment; filename=...'.
    """

    def test_evidence_presigned_url_enforces_attachment_disposition(self):
        analyst = User.objects.create_user(
            email="analyst_attach@scamshield.gov",
            password="TestPassword123!",
            role=Role.ANALYST,
            approval_status=ApprovalStatus.APPROVED,
        )

        report = ScamReport.objects.create(
            status=ReportStatus.PENDING,
            category=ScamCategory.PHISHING,
            platform=Platform.EMAIL,
            message_text="Attachment disposition test narrative.",
        )

        evidence = ReportEvidence.objects.create(
            report=report,
            s3_key="evidence/test-report-id/clean_evidence.pdf",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=1024,
            content_type="application/pdf",
        )

        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://mock-s3.amazonaws.com/evidence/clean_evidence.pdf?sig=test"

        with patch("apps.intel.services.evidence_service.client", return_value=mock_s3):
            results = issue_evidence_presigned_urls(report=report, actor=analyst)

        assert len(results) == 1
        assert results[0]["id"] == str(evidence.id)
        assert results[0]["download_url"] == "https://mock-s3.amazonaws.com/evidence/clean_evidence.pdf?sig=test"

        # Assert generate_presigned_url call arguments
        mock_s3.generate_presigned_url.assert_called_once()
        _, kwargs = mock_s3.generate_presigned_url.call_args
        params = kwargs.get("Params", {})
        assert "ResponseContentDisposition" in params
        assert params["ResponseContentDisposition"].startswith("attachment;")
        assert 'filename="clean_evidence.pdf"' in params["ResponseContentDisposition"]
