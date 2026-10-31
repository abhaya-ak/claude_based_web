import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.broadcasts.models import (
    AdvisorySeverity,
    AdvisoryStatus,
    ThreatAdvisory,
)
from apps.broadcasts.tests.factories import ThreatAdvisoryFactory
from apps.core.enums import AudienceGroup
from apps.intel.tests.factories import VerifiedIndicatorFactory
from apps.reports.models import ScamCategory


@pytest.mark.django_db
class TestThreatAdvisoryConstraints:
    def test_invalid_severity_fails(self):
        """Failing-insert test for ck_adv_severity."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ThreatAdvisoryFactory(severity="URGENT")
        assert "ck_adv_severity" in str(excinfo.value)

        # Positive control: valid severity succeeds
        valid = ThreatAdvisoryFactory(severity=AdvisorySeverity.CRITICAL)
        assert valid.severity == AdvisorySeverity.CRITICAL

    def test_invalid_status_fails(self):
        """Failing-insert test for ck_adv_status."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ThreatAdvisoryFactory(status="QUEUED")
        assert "ck_adv_status" in str(excinfo.value)

        # Positive control: valid status succeeds
        valid = ThreatAdvisoryFactory(status=AdvisoryStatus.PUBLISHED)
        assert valid.status == AdvisoryStatus.PUBLISHED

    def test_invalid_target_audience_fails(self):
        """Failing-insert test for ck_adv_target_audience."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ThreatAdvisoryFactory(target_audience="INVALID")
        assert "ck_adv_target_audience" in str(excinfo.value)

        # Positive control 1: target_audience="ALL" succeeds
        valid_all = ThreatAdvisoryFactory(target_audience="ALL")
        assert valid_all.target_audience == "ALL"

        # Positive control 2: AudienceGroup member succeeds
        valid_group = ThreatAdvisoryFactory(target_audience=AudienceGroup.TEENAGER)
        assert valid_group.target_audience == AudienceGroup.TEENAGER

    def test_body_exceeding_1500_chars_fails(self):
        """Failing-insert test for ck_adv_body_length."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ThreatAdvisoryFactory(body="B" * 1501)
        assert "ck_adv_body_length" in str(excinfo.value)

        # Positive control: exactly 1500 chars succeeds
        valid = ThreatAdvisoryFactory(body="B" * 1500)
        assert len(valid.body) == 1500

    def test_invalid_category_fails(self):
        """Failing-insert test for ck_adv_category."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ThreatAdvisoryFactory(category="INVALID_CAT")
        assert "ck_adv_category" in str(excinfo.value)

        # Positive control 1: valid category succeeds
        valid1 = ThreatAdvisoryFactory(category=ScamCategory.ECOMMERCE_FRAUD)
        assert valid1.category == ScamCategory.ECOMMERCE_FRAUD

        # Positive control 2: category=None succeeds
        valid2 = ThreatAdvisoryFactory(category=None)
        assert valid2.category is None


@pytest.mark.django_db
class TestBoundaryPasses:
    def test_boundary_body_1500_chars(self):
        advisory = ThreatAdvisoryFactory(body="A" * 1500)
        assert len(advisory.body) == 1500

    def test_boundary_sms_text_140_chars(self):
        advisory = ThreatAdvisoryFactory(sms_text="S" * 140)
        assert len(advisory.sms_text) == 140

    def test_boundary_sms_text_none_ok(self):
        advisory = ThreatAdvisoryFactory(sms_text=None)
        assert advisory.sms_text is None

    def test_boundary_published_fields_none_ok(self):
        advisory = ThreatAdvisoryFactory(published_by=None, published_at=None)
        assert advisory.published_by is None
        assert advisory.published_at is None


@pytest.mark.django_db
class TestOnDeleteAndPrivacy:
    def test_created_by_protect_raises_on_delete(self):
        creator = UserFactory(role="ANALYST")
        advisory = ThreatAdvisoryFactory(created_by=creator)

        with pytest.raises(ProtectedError):
            creator.delete()

        assert ThreatAdvisory.objects.filter(id=advisory.id).exists()

    def test_published_by_protect_raises_on_delete(self):
        publisher = UserFactory(role="ADMIN")
        advisory = ThreatAdvisoryFactory(
            published_by=publisher,
            published_at=timezone.now(),
            status=AdvisoryStatus.PUBLISHED,
        )

        with pytest.raises(ProtectedError):
            publisher.delete()

        assert ThreatAdvisory.objects.filter(id=advisory.id).exists()

    def test_related_indicator_set_null_on_delete(self):
        indicator = VerifiedIndicatorFactory()
        advisory = ThreatAdvisoryFactory(related_indicator=indicator)
        assert advisory.related_indicator == indicator

        indicator.delete()
        advisory.refresh_from_db()
        assert advisory.related_indicator is None

    def test_str_never_exposes_pii(self):
        advisory = ThreatAdvisoryFactory(
            title="Urgent Bank Warning",
            body="Confidential incident report text with victim phone 0123456789",
            severity=AdvisorySeverity.CRITICAL,
        )
        adv_str = str(advisory)
        assert "0123456789" not in adv_str
        assert "Confidential incident report" not in adv_str
        assert "Urgent Bank Warning" in adv_str
        assert "CRITICAL" in adv_str
