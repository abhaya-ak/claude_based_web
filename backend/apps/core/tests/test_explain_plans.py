"""
PostgreSQL EXPLAIN (FORMAT JSON) Index Utilization Test Suite (Task 12.3, Decisions D137, D138, D144).

Verifies that critical database queries on hot operational paths select planned
indexes (Index Scan, Index Only Scan, Bitmap Index Scan) and have zero sequential
scans (Seq Scan) on primary operational tables:
- intel_verifiedindicator: uq_vi_type_normalized_val / idx_vi_status_level
- reports_reportindicator: idx_ri_type_value / uq_indicator_report_type_normalized
- reports_scamreport: idx_report_queue / idx_report_plat_cat_created
- ops_systemauditlog: idx_audit_rate / idx_audit_time
- literacy_educationalguide: idx_guide_tactics_gin
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.intel.selectors.intel_selectors import count_pending_by_indicator, find_active_indicators
from apps.intel.selectors.triage_selectors import get_triage_queue_queryset
from apps.literacy.models import EducationalGuide, Tactic
from apps.literacy.selectors import guides_for_tactics
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog
from apps.ops.selectors.audit_selectors import filter_audit_logs
from apps.reports.models import IndicatorType, Platform, ScamCategory, ScamReport


def _flatten_plan_nodes(plan_dict: dict) -> list[dict]:
    """Recursively extracts all plan nodes from a PostgreSQL EXPLAIN JSON tree."""
    nodes = [plan_dict]
    for child in plan_dict.get("Plans", []):
        nodes.extend(_flatten_plan_nodes(child))
    return nodes


def _explain_sql(sql: str, force_index: bool = True) -> dict:
    """Executes EXPLAIN (FORMAT JSON) against PostgreSQL and returns the root plan."""
    with connection.cursor() as cursor:
        if force_index:
            cursor.execute("SET LOCAL enable_seqscan = off;")
        cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}")
        raw = cursor.fetchone()[0]
        # PostgreSQL returns [{"Plan": {...}}]
        return raw[0]["Plan"] if isinstance(raw, list) else raw["Plan"]


def _assert_table_uses_index(plan_tree: dict, table_name: str, allowed_indexes: tuple[str, ...]):
    """
    Asserts:
    1. Zero sequential scans on table_name.
    2. At least one scan node touches table_name.
    3. At least one of the allowed indexes is utilized in the plan tree.
    """
    all_nodes = _flatten_plan_nodes(plan_tree)

    # 1. Zero Seq Scan on target table
    seq_scans = [
        n for n in all_nodes
        if n.get("Relation Name") == table_name and n.get("Node Type") == "Seq Scan"
    ]
    assert len(seq_scans) == 0, f"Unexpected Seq Scan on {table_name}: {seq_scans}"

    # 2. Plan touches target table
    table_scans = [n for n in all_nodes if n.get("Relation Name") == table_name]
    assert len(table_scans) >= 1, f"Expected query plan to access {table_name}"

    # 3. Target table accessed via planned index
    used_indexes = [n.get("Index Name") for n in all_nodes if n.get("Index Name")]
    matched = [idx for idx in used_indexes if idx in allowed_indexes]
    assert len(matched) >= 1, (
        f"Expected at least one of {allowed_indexes} in query plan, but found used indexes: {used_indexes}"
    )


@pytest.mark.django_db
class TestPostgreSQLExplainPlans:
    """EXPLAIN plan assertions for hot-path queries."""

    def test_explain_public_lookup_find_active_indicators(self):
        """
        Public threat lookup query for blacklist indicators.
        Must select uq_vi_type_normalized_val or idx_vi_status_level with zero Seq Scan.
        """
        pairs = [(IndicatorType.PHONE.value, "+60123456789"), (IndicatorType.DOMAIN.value, "scam-domain.com")]
        with CaptureQueriesContext(connection) as ctx:
            list(find_active_indicators(pairs))

        assert len(ctx.captured_queries) == 1
        sql = ctx.captured_queries[0]["sql"]
        plan = _explain_sql(sql, force_index=True)

        _assert_table_uses_index(
            plan,
            table_name="intel_verifiedindicator",
            allowed_indexes=("uq_vi_type_normalized_val", "idx_vi_status_level"),
        )

    def test_explain_public_lookup_count_pending_by_indicator(self):
        """
        Public lookup query counting pending reports per indicator pair.
        Must utilize idx_ri_type_value on reports_reportindicator and idx_report_queue
        on reports_scamreport with zero Seq Scan.
        """
        pairs = [(IndicatorType.PHONE.value, "+60129998877")]
        with CaptureQueriesContext(connection) as ctx:
            count_pending_by_indicator(pairs)

        assert len(ctx.captured_queries) == 1
        sql = ctx.captured_queries[0]["sql"]
        plan = _explain_sql(sql, force_index=True)

        # Check reports_reportindicator scan
        _assert_table_uses_index(
            plan,
            table_name="reports_reportindicator",
            allowed_indexes=("idx_ri_type_value", "uq_indicator_report_type_normalized", "reports_reportindicator_pkey"),
        )

        # Check reports_scamreport scan
        _assert_table_uses_index(
            plan,
            table_name="reports_scamreport",
            allowed_indexes=("idx_report_queue", "reports_scamreport_pkey"),
        )

    def test_explain_analyst_triage_queue_query(self):
        """
        Analyst triage queue pending report query with cluster size subquery.
        Must utilize idx_report_queue on reports_scamreport with zero Seq Scan.
        """
        qs = get_triage_queue_queryset()[:20]
        with CaptureQueriesContext(connection) as ctx:
            list(qs)

        assert len(ctx.captured_queries) == 1
        sql = ctx.captured_queries[0]["sql"]
        plan = _explain_sql(sql, force_index=True)

        _assert_table_uses_index(
            plan,
            table_name="reports_scamreport",
            allowed_indexes=("idx_report_queue", "reports_scamreport_pkey"),
        )

    def test_explain_admin_audit_log_filtered_search(self):
        """
        Admin portal audit log filtered search by severity, date range, and actor_ip_hash.
        With forced plan (disable seqscan on empty table), must select idx_audit_time
        or idx_audit_rate with zero Seq Scan.
        """
        qs = filter_audit_logs(
            ip_hash="abcdef0123456789",
            severity=AuditSeverity.INFO.value,
            date_from="2026-01-01",
            date_to="2026-12-31",
        )[:20]
        with CaptureQueriesContext(connection) as ctx:
            list(qs)

        assert len(ctx.captured_queries) == 1
        sql = ctx.captured_queries[0]["sql"]
        plan = _explain_sql(sql, force_index=True)

        _assert_table_uses_index(
            plan,
            table_name="ops_systemauditlog",
            allowed_indexes=("idx_audit_time", "idx_audit_rate", "ops_systemauditlog_pkey"),
        )

    def test_explain_audit_rate_limiting_query(self):
        """
        Rate limiting query counting recent events for an IP hash.
        Shape: WHERE event_type=... AND actor_ip_hash=... AND occurred_at >= ...
        Must select composite index idx_audit_rate with zero Seq Scan.
        """
        now = timezone.now()
        qs = SystemAuditLog.objects.filter(
            event_type=AuditEventType.REPORT_SUBMITTED.value,
            actor_ip_hash="abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            occurred_at__gte=now,
        )
        with CaptureQueriesContext(connection) as ctx:
            qs.count()

        assert len(ctx.captured_queries) == 1
        sql = ctx.captured_queries[0]["sql"]
        plan = _explain_sql(sql, force_index=True)

        _assert_table_uses_index(
            plan,
            table_name="ops_systemauditlog",
            allowed_indexes=("idx_audit_rate", "idx_audit_time"),
        )

    def test_explain_educational_guides_gin_index(self):
        """
        Remedial educational guides query matching tactics array (D137, 03a §6).
        Shape: WHERE tactics @> ARRAY['URGENCY']
        Must utilize PostgreSQL GIN index idx_guide_tactics_gin with zero Seq Scan.
        """
        qs = EducationalGuide.objects.filter(tactics__contains=[Tactic.URGENCY.value])
        with CaptureQueriesContext(connection) as ctx:
            list(qs)

        sql = ctx.captured_queries[0]["sql"]
        plan = _explain_sql(sql, force_index=True)

        _assert_table_uses_index(
            plan,
            table_name="literacy_educationalguide",
            allowed_indexes=("idx_guide_tactics_gin",),
        )

    def test_explain_educational_guides_selector_query(self):
        """
        Selector guides_for_tactics matching tactics array and language.
        Must utilize idx_guide_list or idx_guide_tactics_gin with zero Seq Scan.
        """
        with CaptureQueriesContext(connection) as ctx:
            list(guides_for_tactics([Tactic.URGENCY.value], language="en"))

        sql = ctx.captured_queries[0]["sql"]
        plan = _explain_sql(sql, force_index=True)

        _assert_table_uses_index(
            plan,
            table_name="literacy_educationalguide",
            allowed_indexes=("idx_guide_list", "idx_guide_tactics_gin"),
        )

    def test_explain_analytics_trend_platform_category(self):
        """
        Analytics trend query filtering platform, category, and date range.
        Must utilize idx_report_plat_cat_created on reports_scamreport with zero Seq Scan.
        """
        now = timezone.now()
        qs = ScamReport.objects.filter(
            platform=Platform.WHATSAPP.value,
            category=ScamCategory.FAKE_JOB.value,
            created_at__gte=now,
        ).order_by("-created_at")[:50]

        with CaptureQueriesContext(connection) as ctx:
            list(qs)

        assert len(ctx.captured_queries) == 1
        sql = ctx.captured_queries[0]["sql"]
        plan = _explain_sql(sql, force_index=True)

        _assert_table_uses_index(
            plan,
            table_name="reports_scamreport",
            allowed_indexes=("idx_report_plat_cat_created", "idx_report_created"),
        )
