import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.intel.models import (
    IndicatorStatus,
    IndicatorType,
    ScamCategory,
    ThreatLevel,
    TriageAction,
    TriageDecision,
    VerifiedIndicator,
)
from apps.intel.tests.factories import TriageDecisionFactory, VerifiedIndicatorFactory
from apps.reports.tests.factories import ScamReportFactory


@pytest.mark.django_db
class TestVerifiedIndicatorConstraints:
    def test_duplicate_type_and_normalized_value_fails(self):
        """Failing-insert test for uq_vi_type_normalized_val."""
        VerifiedIndicatorFactory(
            type=IndicatorType.URL,
            normalized_value="https://phish.example.com/login",
        )

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                VerifiedIndicatorFactory(
                    type=IndicatorType.URL,
                    normalized_value="https://phish.example.com/login",
                )
        assert "uq_vi_type_normalized_val" in str(excinfo.value)

        # Positive control 1: distinct normalized_value succeeds
        distinct = VerifiedIndicatorFactory(
            type=IndicatorType.URL,
            normalized_value="https://phish.example.com/different",
        )
        assert distinct.id is not None

        # Positive control 2 (Amendment E): same normalized_value with a DIFFERENT type succeeds
        diff_type = VerifiedIndicatorFactory(
            type=IndicatorType.DOMAIN,
            normalized_value="https://phish.example.com/login",
        )
        assert diff_type.id is not None
        assert diff_type.type == IndicatorType.DOMAIN

    def test_invalid_indicator_type_fails(self):
        """Failing-insert test for ck_vi_type."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                VerifiedIndicator.objects.create(
                    type="INVALID",
                    normalized_value="+60123456789",
                    display_value="+60•••••789",
                    primary_category=ScamCategory.PHISHING,
                    threat_level=ThreatLevel.HIGH,
                    total_report_count=1,
                    first_seen_at=timezone.now(),
                    last_seen_at=timezone.now(),
                    verified_by=UserFactory(role="ANALYST"),
                    verified_at=timezone.now(),
                )
        assert "ck_vi_type" in str(excinfo.value)

        # Positive control: valid type succeeds
        valid = VerifiedIndicatorFactory(type=IndicatorType.PHONE)
        assert valid.type == IndicatorType.PHONE

    def test_invalid_threat_level_fails(self):
        """Failing-insert test for ck_vi_threat_level."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                VerifiedIndicator.objects.create(
                    type=IndicatorType.PHONE,
                    normalized_value="+60123456788",
                    display_value="+60•••••788",
                    primary_category=ScamCategory.PHISHING,
                    threat_level="EXTREME",
                    total_report_count=1,
                    first_seen_at=timezone.now(),
                    last_seen_at=timezone.now(),
                    verified_by=UserFactory(role="ANALYST"),
                    verified_at=timezone.now(),
                )
        assert "ck_vi_threat_level" in str(excinfo.value)

        # Positive control: valid threat level succeeds
        valid = VerifiedIndicatorFactory(threat_level=ThreatLevel.CRITICAL)
        assert valid.threat_level == ThreatLevel.CRITICAL

    def test_invalid_status_fails(self):
        """Failing-insert test for ck_vi_status."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                VerifiedIndicator.objects.create(
                    type=IndicatorType.PHONE,
                    normalized_value="+60123456787",
                    display_value="+60•••••787",
                    primary_category=ScamCategory.PHISHING,
                    threat_level=ThreatLevel.MEDIUM,
                    total_report_count=1,
                    first_seen_at=timezone.now(),
                    last_seen_at=timezone.now(),
                    status="INACTIVE",
                    verified_by=UserFactory(role="ANALYST"),
                    verified_at=timezone.now(),
                )
        assert "ck_vi_status" in str(excinfo.value)

        # Positive control: valid status succeeds
        valid = VerifiedIndicatorFactory(status=IndicatorStatus.ACTIVE)
        assert valid.status == IndicatorStatus.ACTIVE

    def test_total_report_count_below_one_fails(self):
        """Failing-insert test for ck_vi_total_report_count."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                VerifiedIndicatorFactory(total_report_count=0)
        assert "ck_vi_total_report_count" in str(excinfo.value)

        # Positive control: total_report_count = 1 succeeds
        valid = VerifiedIndicatorFactory(total_report_count=1)
        assert valid.total_report_count == 1

    def test_invalid_primary_category_fails(self):
        """Failing-insert test for ck_vi_primary_category."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                VerifiedIndicator.objects.create(
                    type=IndicatorType.PHONE,
                    normalized_value="+60123456786",
                    display_value="+60•••••786",
                    primary_category="INVALID_CAT",
                    threat_level=ThreatLevel.MEDIUM,
                    total_report_count=1,
                    first_seen_at=timezone.now(),
                    last_seen_at=timezone.now(),
                    verified_by=UserFactory(role="ANALYST"),
                    verified_at=timezone.now(),
                )
        assert "ck_vi_primary_category" in str(excinfo.value)

        # Positive control: valid primary_category succeeds
        valid = VerifiedIndicatorFactory(primary_category=ScamCategory.ECOMMERCE_FRAUD)
        assert valid.primary_category == ScamCategory.ECOMMERCE_FRAUD

    def test_fully_populated_revoked_indicator_succeeds(self):
        """Amendment E: a fully populated REVOKED indicator inserts fine."""
        analyst = UserFactory(role="ANALYST")
        now = timezone.now()
        revoked = VerifiedIndicatorFactory(
            type=IndicatorType.BANK_ACCOUNT,
            normalized_value="0123456789012345678901234567890123456789012345678901234567890123",
            display_value="••••6789",
            primary_category=ScamCategory.IMPERSONATION,
            threat_level=ThreatLevel.HIGH,
            total_report_count=5,
            status=IndicatorStatus.REVOKED,
            public_note="Verified bank account blacklist entry (revoked)",
            revoked_by=analyst,
            revoked_at=now,
            revoke_reason="Bank confirmed account recovered by legitimate owner",
        )
        assert revoked.status == IndicatorStatus.REVOKED
        assert revoked.revoked_by == analyst
        assert revoked.revoke_reason == "Bank confirmed account recovered by legitimate owner"
        assert revoked.public_note == "Verified bank account blacklist entry (revoked)"


@pytest.mark.django_db
class TestTriageDecisionConstraints:
    def test_invalid_triage_action_fails(self):
        """Failing-insert test for ck_triage_action."""
        report = ScamReportFactory()
        analyst = UserFactory(role="ANALYST")

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                TriageDecision.objects.create(
                    report=report,
                    analyst=analyst,
                    action="ESCALATE",
                    reason="Needs supervisor",
                )
        assert "ck_triage_action" in str(excinfo.value)

        # Positive control: valid action succeeds
        valid = TriageDecisionFactory(report=report, analyst=analyst, action=TriageAction.VERIFY)
        assert valid.action == TriageAction.VERIFY

    def test_reject_without_reason_fails(self):
        """Amendment D: for REJECT require reason IS NOT NULL and Length(Trim("reason")) >= 1."""
        report = ScamReportFactory()
        analyst = UserFactory(role="ANALYST")

        # 1. reason=None on REJECT fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                TriageDecision.objects.create(
                    report=report,
                    analyst=analyst,
                    action=TriageAction.REJECT,
                    reason=None,
                )
        assert "ck_triage_reject_reason" in str(excinfo.value)

        # 2. reason="" on REJECT fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                TriageDecision.objects.create(
                    report=report,
                    analyst=analyst,
                    action=TriageAction.REJECT,
                    reason="",
                )
        assert "ck_triage_reject_reason" in str(excinfo.value)

        # 3. reason="   " (whitespace-only) on REJECT fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                TriageDecision.objects.create(
                    report=report,
                    analyst=analyst,
                    action=TriageAction.REJECT,
                    reason="   ",
                )
        assert "ck_triage_reject_reason" in str(excinfo.value)

        # Positive control 1: reason="x" on REJECT passes
        valid_reject = TriageDecision.objects.create(
            report=report,
            analyst=analyst,
            action=TriageAction.REJECT,
            reason="x",
        )
        assert valid_reject.action == TriageAction.REJECT
        assert valid_reject.reason == "x"

        # Positive control 2: VERIFY with reason=None passes
        valid_verify = TriageDecision.objects.create(
            report=report,
            analyst=analyst,
            action=TriageAction.VERIFY,
            reason=None,
        )
        assert valid_verify.action == TriageAction.VERIFY
        assert valid_verify.reason is None


@pytest.mark.django_db
class TestBoundaryPasses:
    def test_boundary_total_report_count_one_ok(self):
        vi = VerifiedIndicatorFactory(total_report_count=1)
        assert vi.total_report_count == 1

    def test_boundary_display_value_128_chars_ok(self):
        val = "D" * 128
        vi = VerifiedIndicatorFactory(display_value=val)
        assert len(vi.display_value) == 128

    def test_boundary_normalized_value_512_chars_ok(self):
        val = "N" * 512
        vi = VerifiedIndicatorFactory(normalized_value=val)
        assert len(vi.normalized_value) == 512

    def test_boundary_public_note_500_chars_ok(self):
        val = "P" * 500
        vi = VerifiedIndicatorFactory(public_note=val)
        assert len(vi.public_note) == 500

    def test_boundary_revoke_reason_300_chars_ok(self):
        val = "R" * 300
        vi = VerifiedIndicatorFactory(
            status=IndicatorStatus.REVOKED,
            revoked_by=UserFactory(role="ANALYST"),
            revoked_at=timezone.now(),
            revoke_reason=val,
        )
        assert len(vi.revoke_reason) == 300

    def test_boundary_triage_reason_500_chars_ok(self):
        val = "T" * 500
        decision = TriageDecisionFactory(
            action=TriageAction.REJECT,
            reason=val,
        )
        assert len(decision.reason) == 500


@pytest.mark.django_db
class TestOnDeleteAndRelationships:
    def test_verified_by_protect_raises_on_delete(self):
        analyst = UserFactory(role="ANALYST")
        vi = VerifiedIndicatorFactory(verified_by=analyst)

        with pytest.raises(ProtectedError):
            analyst.delete()

        assert VerifiedIndicator.objects.filter(id=vi.id).exists()

    def test_revoked_by_set_null_on_user_delete(self):
        analyst = UserFactory(role="ANALYST")
        vi = VerifiedIndicatorFactory(
            status=IndicatorStatus.REVOKED,
            revoked_by=analyst,
            revoked_at=timezone.now(),
            revoke_reason="Revoked due to appeal",
        )
        assert vi.revoked_by == analyst

        analyst.delete()
        vi.refresh_from_db()
        assert vi.revoked_by is None

    def test_triage_analyst_protect_raises_on_delete(self):
        analyst = UserFactory(role="ANALYST")
        decision = TriageDecisionFactory(analyst=analyst)

        with pytest.raises(ProtectedError):
            analyst.delete()

        assert TriageDecision.objects.filter(id=decision.id).exists()

    def test_triage_report_cascade_deletes_decision(self):
        report = ScamReportFactory()
        decision = TriageDecisionFactory(report=report)
        decision_id = decision.id

        report.delete()
        assert not TriageDecision.objects.filter(id=decision_id).exists()

    def test_triage_indicator_set_null_on_delete(self):
        indicator = VerifiedIndicatorFactory()
        decision = TriageDecisionFactory(indicator=indicator)
        assert decision.indicator == indicator

        indicator.delete()
        decision.refresh_from_db()
        assert decision.indicator is None


@pytest.mark.django_db
class TestPrivacy:
    def test_str_never_exposes_pii(self):
        vi = VerifiedIndicatorFactory(
            type=IndicatorType.PHONE,
            normalized_value="+60123456789",
            public_note="Internal investigation note with email suspect@scam.com",
        )
        vi_str = str(vi)
        assert "+60123456789" not in vi_str
        assert "suspect@scam.com" not in vi_str
        assert "PHONE" in vi_str

        decision = TriageDecisionFactory(
            action=TriageAction.REJECT,
            reason="Analyst internal notes mentioning citizen account 9876543210",
        )
        dec_str = str(decision)
        assert "9876543210" not in dec_str
        assert "internal notes" not in dec_str
        assert "REJECT" in dec_str
