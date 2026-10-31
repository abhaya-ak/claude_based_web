"""
Read-only script to dump column names, PostgreSQL types, and nullability
for all 19 application tables.
Uses pg_catalog.format_type(atttypid, atttypmod) to capture full type signatures
including array element types and dimensions.
Used for schema verification and conformance checks against docs/03a.
"""

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

APP_TABLES = [
    # 4.1 accounts_user
    "accounts_user",
    # 4.2 reports_scamreport
    "reports_scamreport",
    # 4.3 reports_reportindicator
    "reports_reportindicator",
    # 4.4 reports_reportevidence
    "reports_reportevidence",
    # 4.5 reports_recoveryplaybook
    "reports_recoveryplaybook",
    # 4.6 intel_verifiedindicator
    "intel_verifiedindicator",
    # 4.7 intel_triagedecision
    "intel_triagedecision",
    # 4.8 alerts_alertsubscription
    "alerts_alertsubscription",
    # 4.9 broadcasts_threatadvisory
    "broadcasts_threatadvisory",
    # 4.10 literacy_educationalguide
    "literacy_educationalguide",
    # 4.11 literacy_guideasset
    "literacy_guideasset",
    # 4.12 literacy_simulatorscenario
    "literacy_simulatorscenario",
    # 4.13 literacy_scenarioredflag
    "literacy_scenarioredflag",
    # 4.14 literacy_simulatorattempt
    "literacy_simulatorattempt",
    # 4.15 literacy_attemptanswer
    "literacy_attemptanswer",
    # 4.16 scanner_heuristicrule
    "scanner_heuristicrule",
    # 4.17 scanner_scannerconfig
    "scanner_scannerconfig",
    # 4.18 scanner_scanresult
    "scanner_scanresult",
    # 4.19 ops_systemauditlog
    "ops_systemauditlog",
]


def dump_schema():
    with connection.cursor() as cursor:
        print(f"Database: {connection.settings_dict['NAME']}")
        print(f"Total app tables to dump: {len(APP_TABLES)}\n")

        for table in APP_TABLES:
            cursor.execute(
                """
                SELECT 
                    a.attname AS column_name,
                    format_type(a.atttypid, a.atttypmod) AS full_type,
                    a.attnotnull,
                    pg_get_expr(d.adbin, d.adrelid) AS column_default
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                WHERE n.nspname = 'public' 
                  AND c.relname = %s
                  AND a.attnum > 0 
                  AND NOT a.attisdropped
                ORDER BY a.attnum;
                """,
                [table],
            )
            rows = cursor.fetchall()
            print(f"=== Table: {table} ({len(rows)} columns) ===")
            if not rows:
                print("  (TABLE NOT FOUND)")
                continue

            for row in rows:
                col_name = row[0]
                type_str = row[1]
                nullable = "NOT NULL" if row[2] else "NULL"
                default_str = f" DEFAULT {row[3]}" if row[3] is not None else ""
                print(f"  - {col_name:<28} {type_str:<28} {nullable:<10}{default_str}")
            print()


if __name__ == "__main__":
    dump_schema()
