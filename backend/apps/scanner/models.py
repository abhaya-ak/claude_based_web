from django.conf import settings
from django.db import models
from django.db.models.functions import Length, Lower, Trim
from django.db.models.lookups import Exact, GreaterThanOrEqual
from django.utils import timezone

from apps.core.models import TimeStampedModel


class RuleType(models.TextChoices):
    KEYWORD = "KEYWORD", "Keyword"
    TLD = "TLD", "TLD"
    SHORTENER = "SHORTENER", "URL Shortener"


class HeuristicRule(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    rule_type = models.CharField(max_length=10, choices=RuleType.choices)
    pattern = models.CharField(max_length=100)
    weight = models.SmallIntegerField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_heuristic_rules",
    )

    class Meta:
        db_table = "scanner_heuristicrule"
        constraints = [
            models.UniqueConstraint(
                fields=["rule_type", "pattern"],
                name="uq_rule_type_pattern",
            ),
            models.CheckConstraint(
                condition=models.Q(rule_type__in=RuleType.values),
                name="ck_rule_type",
            ),
            models.CheckConstraint(
                condition=models.Q(weight__gte=1, weight__lte=50),
                name="ck_rule_weight_range",
            ),
            models.CheckConstraint(
                condition=Exact(models.F("pattern"), Lower("pattern")),
                name="ck_rule_pattern_lowercase",
            ),
            models.CheckConstraint(
                condition=GreaterThanOrEqual(Length(Trim("pattern")), 1),
                name="ck_rule_pattern_not_blank",
            ),
        ]

    def __str__(self):
        # Privacy & safety: do not include raw pattern
        return f"HeuristicRule #{self.id} ({self.rule_type}, weight={self.weight})"


class ScannerConfig(models.Model):
    id = models.SmallIntegerField(primary_key=True, default=1)
    keyword_cap_points = models.SmallIntegerField(default=45)
    ip_url_points = models.SmallIntegerField(default=25)
    prior_pending_points = models.SmallIntegerField(default=20)
    high_priority_threshold = models.SmallIntegerField(default=75)
    ruleset_version = models.IntegerField(default=1)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_scanner_configs",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scanner_scannerconfig"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="ck_config_singleton",
            ),
            models.CheckConstraint(
                condition=models.Q(ruleset_version__gte=1),
                name="ck_config_ruleset_version",
            ),
            models.CheckConstraint(
                condition=models.Q(keyword_cap_points__gte=0, keyword_cap_points__lte=100),
                name="ck_config_keyword_cap_points",
            ),
            models.CheckConstraint(
                condition=models.Q(ip_url_points__gte=0, ip_url_points__lte=100),
                name="ck_config_ip_url_points",
            ),
            models.CheckConstraint(
                condition=models.Q(prior_pending_points__gte=0, prior_pending_points__lte=100),
                name="ck_config_prior_pending_points",
            ),
            models.CheckConstraint(
                condition=models.Q(high_priority_threshold__gte=1, high_priority_threshold__lte=100),
                name="ck_config_high_priority_threshold",
            ),
        ]

    def __str__(self):
        return f"ScannerConfig(ruleset_version={self.ruleset_version})"


class ScanResult(models.Model):
    id = models.BigAutoField(primary_key=True)
    report = models.OneToOneField(
        "reports.ScamReport",
        on_delete=models.CASCADE,
        related_name="scan_result",
    )
    ruleset_version = models.IntegerField()
    risk_score = models.SmallIntegerField()
    breakdown = models.JSONField(default=list)
    is_high_priority = models.BooleanField()
    lambda_request_id = models.CharField(max_length=64, null=True, blank=True)
    scanned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "scanner_scanresult"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(risk_score__gte=0, risk_score__lte=100),
                name="ck_scan_risk_score_range",
            ),
            models.CheckConstraint(
                condition=Exact(
                    models.Func("breakdown", function="jsonb_typeof", output_field=models.CharField()),
                    models.Value("array"),
                ),
                name="ck_scan_breakdown_is_array",
            ),
        ]

    def __str__(self):
        # Privacy & safety: do not include breakdown contents
        return f"ScanResult #{self.id} for report {self.report_id} (score={self.risk_score})"
