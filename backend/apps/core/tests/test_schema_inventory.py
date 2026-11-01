"""
Schema Inventory Safety-Net Test (Decision D20).

This test suite inspects the live PostgreSQL database catalog
(information_schema.tables, pg_constraint, pg_indexes, pg_index) to guarantee:
1. Exact set of 27 public tables (19 app tables + 6 Django internal tables).
2. No duplicate index column lists on any table (catches redundant FK indexes).
3. Exact set of named constraints (ck_*, uq_*) and indexes (idx_*, uq_*) per app table.

HOW TO UPDATE ON LEGITIMATE SCHEMA CHANGES:
When a future phase adds, modifies, or removes a table, constraint, or index
with explicit approval, the developer must update EXPECTED_PUBLIC_TABLES and/or
EXPECTED_SCHEMA_INVENTORY in this file to match the newly frozen contract.
"""

from collections import defaultdict

import pytest
from django.db import connection

EXPECTED_APP_TABLES = {
    # accounts
    "accounts_user",
    # reports
    "reports_scamreport",
    "reports_reportindicator",
    "reports_reportevidence",
    "reports_recoveryplaybook",
    # intel
    "intel_verifiedindicator",
    "intel_triagedecision",
    # alerts
    "alerts_alertsubscription",
    # broadcasts
    "broadcasts_threatadvisory",
    # literacy
    "literacy_educationalguide",
    "literacy_guideasset",
    "literacy_simulatorscenario",
    "literacy_scenarioredflag",
    "literacy_simulatorattempt",
    "literacy_attemptanswer",
    # scanner
    "scanner_heuristicrule",
    "scanner_scannerconfig",
    "scanner_scanresult",
    # ops
    "ops_systemauditlog",
}

EXPECTED_DJANGO_TABLES = {
    "django_migrations",
    "django_content_type",
    "django_session",
    "auth_group",
    "auth_group_permissions",
    "auth_permission",
    "token_blacklist_outstandingtoken",
    "token_blacklist_blacklistedtoken",
}

EXPECTED_PUBLIC_TABLES = EXPECTED_APP_TABLES | EXPECTED_DJANGO_TABLES

EXPECTED_SCHEMA_INVENTORY = {
    "accounts_user": {
        "constraints": [
            "ck_user_approval_status",
            "ck_user_citizen_approved",
            "ck_user_role",
        ],
        "indexes": [
            "uq_user_email_lower",
        ],
    },
    "reports_scamreport": {
        "constraints": [
            "ck_report_anon_reporter",
            "ck_report_category",
            "ck_report_financial_loss_non_negative",
            "ck_report_message_text_length",
            "ck_report_payment_method",
            "ck_report_platform",
            "ck_report_risk_score_range",
            "ck_report_scan_status",
            "ck_report_status",
        ],
        "indexes": [
            "idx_report_created",
            "idx_report_geo_created",
            "idx_report_plat_cat_created",
            "idx_report_queue",
            "idx_report_reporter",
            "idx_report_scan_pending",
            "idx_report_status_created",
        ],
    },
    "reports_reportindicator": {
        "constraints": [
            "ck_indicator_type",
            "uq_indicator_report_type_normalized",
        ],
        "indexes": [
            "idx_ri_type_value",
            "idx_ri_verified",
            "uq_indicator_report_type_normalized",
        ],
    },
    "reports_reportevidence": {
        "constraints": [
            "ck_evidence_content_type",
            "ck_evidence_size_bytes",
        ],
        "indexes": [],
    },
    "reports_recoveryplaybook": {
        "constraints": [
            "ck_playbook_category",
            "ck_playbook_payment_method",
        ],
        "indexes": [],
    },
    "intel_verifiedindicator": {
        "constraints": [
            "ck_vi_primary_category",
            "ck_vi_status",
            "ck_vi_threat_level",
            "ck_vi_total_report_count",
            "ck_vi_type",
            "uq_vi_type_normalized_val",
        ],
        "indexes": [
            "idx_vi_last_seen",
            "idx_vi_status_level",
            "uq_vi_type_normalized_val",
        ],
    },
    "intel_triagedecision": {
        "constraints": [
            "ck_triage_action",
            "ck_triage_reject_reason",
        ],
        "indexes": [],
    },
    "alerts_alertsubscription": {
        "constraints": [
            "ck_sub_audience",
            "ck_sub_categories_elements",
            "ck_sub_channel",
            "ck_sub_status",
            "uq_sub_channel_endpoint_aud",
        ],
        "indexes": [
            "idx_sub_status_audience",
            "uq_sub_channel_endpoint_aud",
        ],
    },
    "broadcasts_threatadvisory": {
        "constraints": [
            "ck_adv_body_length",
            "ck_adv_category",
            "ck_adv_severity",
            "ck_adv_status",
            "ck_adv_target_audience",
        ],
        "indexes": [
            "idx_adv_status_published",
        ],
    },
    "literacy_educationalguide": {
        "constraints": [
            "ck_guide_audience_groups",
            "ck_guide_language",
            "ck_guide_published_audience",
            "ck_guide_published_timestamp",
            "ck_guide_readability_mode",
            "ck_guide_status",
            "ck_guide_tactics",
        ],
        "indexes": [
            "idx_guide_audience_gin",
            "idx_guide_list",
            "idx_guide_tactics_gin",
        ],
    },
    "literacy_guideasset": {
        "constraints": [
            "ck_asset_duration_positive",
            "ck_asset_image_alt_text",
            "ck_asset_size_bytes_positive",
            "ck_asset_type",
        ],
        "indexes": [],
    },
    "literacy_simulatorscenario": {
        "constraints": [
            "ck_scenario_channel",
            "ck_scenario_difficulty",
            "ck_scenario_legit_tactic_none",
            "ck_scenario_scam_has_tactic",
            "ck_scenario_status",
            "ck_scenario_tactic",
        ],
        "indexes": [
            "idx_scn_status",
        ],
    },
    "literacy_scenarioredflag": {
        "constraints": [
            "ck_flag_code",
            "ck_flag_h_pct_range",
            "ck_flag_w_pct_range",
            "ck_flag_x_pct_range",
            "ck_flag_x_plus_w_bound",
            "ck_flag_y_pct_range",
            "ck_flag_y_plus_h_bound",
        ],
        "indexes": [],
    },
    "literacy_simulatorattempt": {
        "constraints": [
            "ck_attempt_completed_fields",
            "ck_attempt_scenario_count",
            "ck_attempt_score_pct_range",
            "ck_attempt_status",
            "ck_attempt_user_or_session",
        ],
        "indexes": [
            "idx_attempt_user",
        ],
    },
    "literacy_attemptanswer": {
        "constraints": [
            "ck_answer_flag_only_if_scam",
            "ck_answer_selected_flag_code",
            "uq_answer_attempt_scenario",
        ],
        "indexes": [
            "uq_answer_attempt_scenario",
        ],
    },
    "scanner_heuristicrule": {
        "constraints": [
            "ck_rule_pattern_lowercase",
            "ck_rule_pattern_not_blank",
            "ck_rule_type",
            "ck_rule_weight_range",
            "uq_rule_type_pattern",
        ],
        "indexes": [
            "uq_rule_type_pattern",
        ],
    },
    "scanner_scannerconfig": {
        "constraints": [
            "ck_config_high_priority_threshold",
            "ck_config_ip_url_points",
            "ck_config_keyword_cap_points",
            "ck_config_prior_pending_points",
            "ck_config_ruleset_version",
            "ck_config_singleton",
        ],
        "indexes": [],
    },
    "scanner_scanresult": {
        "constraints": [
            "ck_scan_breakdown_is_array",
            "ck_scan_risk_score_range",
        ],
        "indexes": [],
    },
    "ops_systemauditlog": {
        "constraints": [
            "ck_audit_event_type",
            "ck_audit_metadata_is_object",
            "ck_audit_severity",
            "ck_audit_target_pair",
        ],
        "indexes": [
            "idx_audit_actor",
            "idx_audit_rate",
            "idx_audit_time",
        ],
    },
}


@pytest.mark.django_db
def test_public_tables_exact_set():
    """Verify that schema public contains exactly the 19 app + 6 Django tables."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """
        )
        actual_tables = {row[0] for row in cursor.fetchall()}

    missing = sorted(list(EXPECTED_PUBLIC_TABLES - actual_tables))
    unexpected = sorted(list(actual_tables - EXPECTED_PUBLIC_TABLES))

    assert not missing and not unexpected, (
        f"Public table inventory mismatch!\n"
        f"  Missing tables ({len(missing)}): {missing}\n"
        f"  Unexpected tables ({len(unexpected)}): {unexpected}"
    )

    # Explicit ban check: PermissionsMixin tables must NOT exist
    assert "accounts_user_groups" not in actual_tables
    assert "accounts_user_user_permissions" not in actual_tables
    assert len(actual_tables) == 27  # D41: 19 app + 8 Django/third-party


@pytest.mark.django_db
def test_no_duplicate_index_column_lists():
    """
    Verify that no table has two indexes on identical column lists.
    Catches redundant FK indexes (e.g. Django auto FK index + custom explicit index).
    Excludes PostgreSQL automatic _like pattern indexes created for varchar columns.
    """
    query = """
        SELECT
            t.relname AS table_name,
            i.relname AS index_name,
            ix.indkey::text AS indkey
        FROM pg_index ix
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
        ORDER BY t.relname, i.relname;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    table_indexes = defaultdict(list)
    for table_name, index_name, indkey in rows:
        if index_name.endswith("_like"):
            continue
        table_indexes[table_name].append((index_name, indkey))

    duplicates = []
    for table_name, index_list in table_indexes.items():
        seen_keys = {}
        for index_name, indkey in index_list:
            if indkey in seen_keys:
                duplicates.append({
                    "table": table_name,
                    "duplicate_index": index_name,
                    "existing_index": seen_keys[indkey],
                    "columns_key": indkey,
                })
            else:
                seen_keys[indkey] = index_name

    assert not duplicates, f"Found duplicate indexes with identical column lists: {duplicates}"


@pytest.mark.django_db
def test_named_constraints_and_indexes_exact_inventory():
    """
    Verify that each of the 19 app tables has exactly the expected named
    constraints (ck_*, uq_*) and named indexes (idx_*, uq_*).
    """
    errors = []

    with connection.cursor() as cursor:
        for table_name, expected_data in EXPECTED_SCHEMA_INVENTORY.items():
            expected_constraints = set(expected_data["constraints"])
            expected_indexes = set(expected_data["indexes"])

            # Query actual constraints (ck_*, uq_*)
            cursor.execute(
                """
                SELECT conname
                FROM pg_constraint
                JOIN pg_class c ON c.oid = conrelid
                WHERE c.relname = %s AND (conname LIKE 'ck_%%' OR conname LIKE 'uq_%%')
                ORDER BY conname;
                """,
                [table_name],
            )
            actual_constraints = {row[0] for row in cursor.fetchall()}

            # Query actual indexes (idx_*, uq_*)
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = %s AND (indexname LIKE 'idx_%%' OR indexname LIKE 'uq_%%')
                ORDER BY indexname;
                """,
                [table_name],
            )
            actual_indexes = {row[0] for row in cursor.fetchall()}

            missing_con = sorted(list(expected_constraints - actual_constraints))
            unexpected_con = sorted(list(actual_constraints - expected_constraints))
            missing_idx = sorted(list(expected_indexes - actual_indexes))
            unexpected_idx = sorted(list(actual_indexes - expected_indexes))

            if missing_con or unexpected_con or missing_idx or unexpected_idx:
                errors.append(
                    f"\nTable: {table_name}\n"
                    f"  Missing constraints ({len(missing_con)}): {missing_con}\n"
                    f"  Unexpected constraints ({len(unexpected_con)}): {unexpected_con}\n"
                    f"  Missing indexes ({len(missing_idx)}): {missing_idx}\n"
                    f"  Unexpected indexes ({len(unexpected_idx)}): {unexpected_idx}"
                )

    assert not errors, "Schema inventory mismatch:\n" + "\n".join(errors)
