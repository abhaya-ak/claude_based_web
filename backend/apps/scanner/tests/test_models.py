import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.accounts.tests.factories import UserFactory
from apps.reports.tests.factories import ScamReportFactory
from apps.scanner.models import (
    RuleType,
    ScannerConfig,
    ScanResult,
)
from apps.scanner.tests.factories import (
    HeuristicRuleFactory,
    ScanResultFactory,
)


@pytest.mark.django_db
class TestHeuristicRuleConstraints:
    def test_invalid_rule_type_fails(self):
        """Failing-insert test for ck_rule_type."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                HeuristicRuleFactory(rule_type="REGEX")
        assert "ck_rule_type" in str(excinfo.value)

        # Positive control: valid rule_type succeeds
        valid = HeuristicRuleFactory(rule_type=RuleType.KEYWORD)
        assert valid.rule_type == RuleType.KEYWORD

    def test_weight_boundaries(self):
        """Failing and passing tests for ck_rule_weight_range (1..50)."""
        # Failing case 1: 0
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                HeuristicRuleFactory(weight=0)
        assert "ck_rule_weight_range" in str(excinfo.value)

        # Failing case 2: 51
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                HeuristicRuleFactory(weight=51)
        assert "ck_rule_weight_range" in str(excinfo.value)

        # Positive controls: 1 and 50 succeed
        w1 = HeuristicRuleFactory(weight=1)
        w50 = HeuristicRuleFactory(weight=50)
        assert w1.weight == 1
        assert w50.weight == 50

    def test_pattern_lowercase_rule(self):
        """D18: Failing and passing tests for ck_rule_pattern_lowercase."""
        # Failing case 1: uppercase
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                HeuristicRuleFactory(pattern="URGENT")
        assert "ck_rule_pattern_lowercase" in str(excinfo.value)

        # Failing case 2: mixed case
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                HeuristicRuleFactory(pattern="UrgentAction")
        assert "ck_rule_pattern_lowercase" in str(excinfo.value)

        # Positive control: strictly lowercase succeeds
        valid = HeuristicRuleFactory(pattern="urgent-action")
        assert valid.pattern == "urgent-action"

    def test_pattern_not_blank_rule(self):
        """D18: Failing and passing tests for ck_rule_pattern_not_blank."""
        # Failing case 1: empty string
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                HeuristicRuleFactory(pattern="")
        assert "ck_rule_pattern_not_blank" in str(excinfo.value)

        # Failing case 2: whitespace only
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                HeuristicRuleFactory(pattern="   ")
        assert "ck_rule_pattern_not_blank" in str(excinfo.value)

        # Positive control: single non-whitespace character succeeds
        valid = HeuristicRuleFactory(pattern="a")
        assert valid.pattern == "a"

    def test_duplicate_rule_type_and_pattern_fails(self):
        """Failing-insert test for uq_rule_type_pattern."""
        HeuristicRuleFactory(rule_type=RuleType.KEYWORD, pattern="phishing-link")

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                HeuristicRuleFactory(rule_type=RuleType.KEYWORD, pattern="phishing-link")
        assert "uq_rule_type_pattern" in str(excinfo.value)

        # Positive control: same pattern with different rule_type succeeds
        diff_type = HeuristicRuleFactory(rule_type=RuleType.TLD, pattern="phishing-link")
        assert diff_type.rule_type == RuleType.TLD


@pytest.mark.django_db
class TestScannerConfigConstraints:
    def test_seeded_singleton_exists(self):
        """D19: The ScannerConfig singleton row id=1 exists after migrations."""
        config = ScannerConfig.objects.get(id=1)
        assert config.ruleset_version == 1
        assert config.keyword_cap_points == 45
        assert config.ip_url_points == 25
        assert config.prior_pending_points == 20
        assert config.high_priority_threshold == 75

    def test_singleton_id_constraint(self):
        """Amendment B: id=2 failing insert; id=1 passes when existing row is deleted first."""
        # Failing case: id=2 fails ck_config_singleton
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.create(id=2)
        assert "ck_config_singleton" in str(excinfo.value)

        # Positive control: inside its own atomic transaction, delete id=1, then insert id=1
        with transaction.atomic():
            ScannerConfig.objects.filter(id=1).delete()
            created = ScannerConfig.objects.create(id=1, ruleset_version=1)
            assert created.id == 1
            transaction.set_rollback(True)

    def test_ruleset_version_positive_boundary(self):
        """Amendment B: ruleset_version boundary via UPDATE on seeded row."""
        # Failing case: ruleset_version = 0 fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(ruleset_version=0)
        assert "ck_config_ruleset_version" in str(excinfo.value)

        # Positive control: ruleset_version = 1 passes
        ScannerConfig.objects.filter(id=1).update(ruleset_version=1)
        assert ScannerConfig.objects.get(id=1).ruleset_version == 1

    def test_keyword_cap_points_boundaries(self):
        """Amendment B: keyword_cap_points 0/100 pass, -1/101 fail."""
        # Failing case 1: -1
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(keyword_cap_points=-1)
        assert "ck_config_keyword_cap_points" in str(excinfo.value)

        # Failing case 2: 101
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(keyword_cap_points=101)
        assert "ck_config_keyword_cap_points" in str(excinfo.value)

        # Positive controls: 0 and 100 pass
        ScannerConfig.objects.filter(id=1).update(keyword_cap_points=0)
        assert ScannerConfig.objects.get(id=1).keyword_cap_points == 0
        ScannerConfig.objects.filter(id=1).update(keyword_cap_points=100)
        assert ScannerConfig.objects.get(id=1).keyword_cap_points == 100

    def test_ip_url_points_boundaries(self):
        """Amendment B: ip_url_points 0/100 pass, -1/101 fail."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(ip_url_points=-1)
        assert "ck_config_ip_url_points" in str(excinfo.value)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(ip_url_points=101)
        assert "ck_config_ip_url_points" in str(excinfo.value)

        ScannerConfig.objects.filter(id=1).update(ip_url_points=0)
        assert ScannerConfig.objects.get(id=1).ip_url_points == 0
        ScannerConfig.objects.filter(id=1).update(ip_url_points=100)
        assert ScannerConfig.objects.get(id=1).ip_url_points == 100

    def test_prior_pending_points_boundaries(self):
        """Amendment B: prior_pending_points 0/100 pass, -1/101 fail."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(prior_pending_points=-1)
        assert "ck_config_prior_pending_points" in str(excinfo.value)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(prior_pending_points=101)
        assert "ck_config_prior_pending_points" in str(excinfo.value)

        ScannerConfig.objects.filter(id=1).update(prior_pending_points=0)
        assert ScannerConfig.objects.get(id=1).prior_pending_points == 0
        ScannerConfig.objects.filter(id=1).update(prior_pending_points=100)
        assert ScannerConfig.objects.get(id=1).prior_pending_points == 100

    def test_high_priority_threshold_boundaries(self):
        """Amendment B: high_priority_threshold 1/100 pass, 0/101 fail."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(high_priority_threshold=0)
        assert "ck_config_high_priority_threshold" in str(excinfo.value)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScannerConfig.objects.filter(id=1).update(high_priority_threshold=101)
        assert "ck_config_high_priority_threshold" in str(excinfo.value)

        ScannerConfig.objects.filter(id=1).update(high_priority_threshold=1)
        assert ScannerConfig.objects.get(id=1).high_priority_threshold == 1
        ScannerConfig.objects.filter(id=1).update(high_priority_threshold=100)
        assert ScannerConfig.objects.get(id=1).high_priority_threshold == 100


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
class TestScannerConfigSerializedRollback:
    def test_seeded_singleton_survives_transaction_tests(self):
        """Amendment C: Proves the seeded ScannerConfig row survives tests with serialized_rollback=True."""
        config = ScannerConfig.objects.filter(id=1).first()
        assert config is not None
        assert config.id == 1


@pytest.mark.django_db
class TestScanResultConstraints:
    def test_duplicate_report_fails(self):
        """Failing-insert test for one-to-one report."""
        report = ScamReportFactory()
        ScanResultFactory(report=report)

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScanResultFactory(report=report)
        assert "report_id" in str(excinfo.value)

        # Positive control: different report succeeds
        report2 = ScamReportFactory()
        valid2 = ScanResultFactory(report=report2)
        assert valid2.report_id == report2.id

    def test_risk_score_boundaries(self):
        """Failing and passing tests for ck_scan_risk_score_range (0..100)."""
        report1 = ScamReportFactory()
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScanResultFactory(report=report1, risk_score=-1)
        assert "ck_scan_risk_score_range" in str(excinfo.value)

        report2 = ScamReportFactory()
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScanResultFactory(report=report2, risk_score=101)
        assert "ck_scan_risk_score_range" in str(excinfo.value)

        valid_0 = ScanResultFactory(report=report1, risk_score=0)
        valid_100 = ScanResultFactory(report=report2, risk_score=100)
        assert valid_0.risk_score == 0
        assert valid_100.risk_score == 100

    def test_breakdown_is_json_array(self):
        """D18 & Amendment E: jsonb_typeof(breakdown) = 'array'."""
        report1 = ScamReportFactory()
        # Failing case 1: JSON object {}
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScanResultFactory(report=report1, breakdown={"rule": "urgent"})
        assert "ck_scan_breakdown_is_array" in str(excinfo.value)

        # Failing case 2: JSON string
        report2 = ScamReportFactory()
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScanResultFactory(report=report2, breakdown="urgent")
        assert "ck_scan_breakdown_is_array" in str(excinfo.value)

        # Positive control 1: empty list []
        valid_empty = ScanResultFactory(report=report1, breakdown=[])
        assert valid_empty.breakdown == []

        # Positive control 2: list with items
        valid_items = ScanResultFactory(report=report2, breakdown=[{"points": 15}])
        assert len(valid_items.breakdown) == 1

    def test_breakdown_none_behavior(self):
        """Amendment E: Test breakdown=None to report whether NOT NULL or check constraint fires."""
        report = ScamReportFactory()
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                ScanResultFactory(report=report, breakdown=None)
        err = str(excinfo.value).lower()
        # Column has NOT NULL, so PostgreSQL raises not-null constraint violation
        assert "null" in err and "breakdown" in err


@pytest.mark.django_db
class TestScannerBoundariesAndRelationships:
    def test_heuristic_rule_author_protect(self):
        """on_delete PROTECT on HeuristicRule.created_by raises ProtectedError."""
        author = UserFactory(role="ADMIN")
        rule = HeuristicRuleFactory(created_by=author)
        assert rule.created_by_id == author.id

        with pytest.raises(ProtectedError):
            author.delete()

    def test_scanner_config_updater_set_null(self):
        """on_delete SET_NULL on ScannerConfig.updated_by nulls the column."""
        updater = UserFactory(role="ADMIN")
        ScannerConfig.objects.filter(id=1).update(updated_by=updater)
        config = ScannerConfig.objects.get(id=1)
        assert config.updated_by_id == updater.id

        updater.delete()

        config.refresh_from_db()
        assert config.updated_by is None

    def test_scan_result_report_cascade(self):
        """on_delete CASCADE on ScanResult.report deletes ScanResult."""
        report = ScamReportFactory()
        scan = ScanResultFactory(report=report)
        scan_id = scan.id

        assert ScanResult.objects.filter(id=scan_id).exists()

        report.delete()

        assert not ScanResult.objects.filter(id=scan_id).exists()

    def test_privacy_rule_str(self):
        """HeuristicRule.__str__ must not leak rule pattern."""
        secret_pattern = "secret-malicious-regex"
        rule = HeuristicRuleFactory(pattern=secret_pattern, weight=25)
        str_rep = str(rule)
        assert "HeuristicRule" in str_rep
        assert "25" in str_rep
        assert secret_pattern not in str_rep

    def test_privacy_scan_result_str(self):
        """ScanResult.__str__ must not leak breakdown contents."""
        report = ScamReportFactory()
        scan = ScanResultFactory(
            report=report,
            risk_score=85,
            breakdown=[{"secret_token": "EXPOSE_ME"}],
        )
        str_rep = str(scan)
        assert "85" in str_rep
        assert str(report.id) in str_rep
        assert "EXPOSE_ME" not in str_rep
