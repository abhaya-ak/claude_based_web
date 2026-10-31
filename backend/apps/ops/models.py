from django.conf import settings
from django.db import models
from django.db.models.lookups import Exact
from django.utils import timezone


class AuditEventType(models.TextChoices):
    REPORT_SUBMITTED = "REPORT_SUBMITTED", "Report Submitted"
    RATE_LIMIT_BLOCK = "RATE_LIMIT_BLOCK", "Rate Limit Block"
    LOGIN_FAILURE = "LOGIN_FAILURE", "Login Failure"
    LOGIN_SUCCESS = "LOGIN_SUCCESS", "Login Success"
    STAFF_REGISTERED = "STAFF_REGISTERED", "Staff Registered"
    ROLE_APPROVED = "ROLE_APPROVED", "Role Approved"
    ROLE_REJECTED = "ROLE_REJECTED", "Role Rejected"
    EVIDENCE_URL_ISSUED = "EVIDENCE_URL_ISSUED", "Evidence URL Issued"
    INDICATOR_VERIFIED = "INDICATOR_VERIFIED", "Indicator Verified"
    REPORT_REJECTED = "REPORT_REJECTED", "Report Rejected"
    INDICATOR_REVOKED = "INDICATOR_REVOKED", "Indicator Revoked"
    ADVISORY_PUBLISHED = "ADVISORY_PUBLISHED", "Advisory Published"
    RULE_CHANGED = "RULE_CHANGED", "Rule Changed"
    CONFIG_CHANGED = "CONFIG_CHANGED", "Config Changed"
    SCAN_FAILED = "SCAN_FAILED", "Scan Failed"


class AuditSeverity(models.TextChoices):
    INFO = "INFO", "Info"
    WARN = "WARN", "Warning"
    ALERT = "ALERT", "Alert"


class SystemAuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        db_index=False,
    )
    actor_ip_hash = models.CharField(max_length=64, null=True, blank=True)
    event_type = models.CharField(max_length=40, choices=AuditEventType.choices)
    severity = models.CharField(max_length=5, choices=AuditSeverity.choices)
    target_type = models.CharField(max_length=40, null=True, blank=True)
    target_id = models.CharField(max_length=64, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    request_id = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "ops_systemauditlog"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(event_type__in=AuditEventType.values),
                name="ck_audit_event_type",
            ),
            models.CheckConstraint(
                condition=models.Q(severity__in=AuditSeverity.values),
                name="ck_audit_severity",
            ),
            models.CheckConstraint(
                condition=Exact(
                    models.Func("metadata", function="jsonb_typeof", output_field=models.CharField()),
                    models.Value("object"),
                ),
                name="ck_audit_metadata_is_object",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(target_type__isnull=True, target_id__isnull=True)
                    | models.Q(target_type__isnull=False, target_id__isnull=False)
                ),
                name="ck_audit_target_pair",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event_type", "actor_ip_hash", "-occurred_at"],
                name="idx_audit_rate",
            ),
            models.Index(
                fields=["occurred_at"],
                name="idx_audit_time",
            ),
            models.Index(
                fields=["actor", "-occurred_at"],
                name="idx_audit_actor",
            ),
        ]

    def __str__(self):
        # Privacy & safety: do not include metadata or actor_ip_hash
        return f"AuditLog #{self.id}: {self.event_type} [{self.severity}] at {self.occurred_at}"
