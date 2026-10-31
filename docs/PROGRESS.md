# PROGRESS (the agent reads this at session start and updates it at the end of every task)

## Current phase
Phase 1B — Models + migrations (done, merge pending)

## Status
| Phase | Owner | Status | Commit/PR | Notes |
|---|---|---|---|---|
| 0 Governance | all | done | 34a26cf | Task 0 done; repo setup, rules, contracts frozen |
| 1A DB design review | all | done | 34a26cf | Design frozen, contracts merged |
| 1B Models + migrations | all | done, merge pending | | 19 app tables, 168 tests, ERD + schema inventory gate complete |
| 2 Scaffold | S4 | todo | | |
| 3 Auth/RBAC | S4 | todo | | |
| M0 Walking skeleton deployed to AWS | S4 | todo | | |
| 4 Reports | S1 | todo | | |
| 5 Scanner | S4 | todo | | |
| 6 Triage | S2 | todo | | |
| 7 Lookup + alerts | S1 | todo | | |
| 8 Analytics + broadcast | S2 | todo | | |
| 9 Literacy CMS | S3 | todo | | |
| 10 Simulator | S3 | todo | | |
| 11 Ops/telemetry | S4 | todo | | |
| 12 Hardening | all | todo | | |
| 13 Containerise + deploy | S4 | todo | | |
| F Frontend phases | all | blocked until frontend doc exists | | |

## Decisions made (consolidated catalogue)

| Decision | Summary | Evidence | Status |
|---|---|---|---|
| **D1** | User indicator limit (max 5) applies to citizen inputs; derived DOMAIN rows excluded (max 10 total); enforced in service | Phase 1A review, `docs/PROGRESS.md` | Approved |
| **D2** | Dedicated `INDICATOR_HMAC_KEY` for BANK_ACCOUNT hashing; `HMAC_IP_SALT` for IP hashing; raw_value retained for migrations | `docs/02-project-architecture.md` §10.4, `docs/03a-database-design.md` §4.3 | Approved |
| **D3** | Scanner point values and thresholds in FR-4.1.3 are defaults editable by admin via ScannerConfig; scoring formula fixed | Phase 1A review, `docs/PROGRESS.md` | Approved |
| **D4** | Unified `AudienceGroup` enum (`GENERAL`, `ELDERLY`, `TEENAGER`, `NON_TECH`) across alerts, advisories, guides; `ALL` allowed on advisories | `apps/core/enums.py:AudienceGroup`, `apps/alerts/models.py:ck_sub_audience` | Approved |
| **D5** | Bank account normalisation strips spaces/dashes/dots; keeps digits with leading zeros; no bank-specific format rules | Phase 1A review, `docs/PROGRESS.md` | Approved |
| **D6** | Server-side evidence uploads retained for Phase 12 evaluation; SMS alerting behind feature flag, OFF by default | Phase 1A review, `docs/PROGRESS.md` | Approved |
| **D7** | User `email` has `unique=True` on model field and functional `Lower('email')` unique index (`uq_user_email_lower`); `UserManager` lowercases email; User model extends `AbstractBaseUser` only (no `PermissionsMixin`) | `apps/accounts/models.py:uq_user_email_lower`, migration `accounts/0001_initial.py` | Implemented |
| **D8** | Python 3.13 standardized across dev environments, Docker base images (`python:3.13-slim`), and runtime configurations | `pyproject.toml`, `docker-compose.yml`, commit `415b006` | Implemented |
| **D9** | reports migration 0002 adds ReportIndicator.verified_indicator after intel 0001 exists | migration `reports/0002_reportindicator_verified_indicator_and_more.py` | Implemented |
| **D10** | Truncated `idx_report_platform_cat_created` to `idx_report_plat_cat_created` to fit Django's 30-char index name limit | `apps/reports/models.py:idx_report_plat_cat_created`, migration `reports/0001_initial.py` | Implemented |
| **D11** | Shared `AudienceGroup` enum in `apps/core/enums.py`; `ScamCategory` imported from `apps.reports.models` | `apps/core/enums.py`, `apps/alerts/models.py`, `apps/broadcasts/models.py`, `apps/literacy/models.py` | Implemented |
| **D12** | `ThreatAdvisory.published_by` FK uses `on_delete=models.PROTECT` per staff FK convention in 03a §1 | `apps/broadcasts/models.py:published_by`, migration `broadcasts/0001_initial.py` | Implemented |
| **D13** | `ck_sub_categories_elements` (`<@` array containment against valid `ScamCategory` values) on `AlertSubscription.categories` | `apps/alerts/models.py:ck_sub_categories_elements`, migration `alerts/0001_initial.py` | Implemented |
| **D14** | Guides array containment checks (`<@`) for `audience_groups` and `tactics`; enum checks; `GuideAsset` IMAGE trimmed alt_text | `apps/literacy/models.py:ck_guide_audience_groups`, `ck_guide_tactics`, `ck_asset_image_alt_text` | Implemented |
| **D15** | `ck_guide_published_audience` (cardinality >= 1), `ck_guide_published_timestamp` (published_at NOT NULL), `ck_asset_duration_positive` (> 0) | `apps/literacy/models.py:ck_guide_published_audience`, `ck_guide_published_timestamp`, `ck_asset_duration_positive` | Implemented |
| **D16** | `ck_scenario_scam_has_tactic`; `ScenarioRedFlag` w_pct/h_pct > 0; `SimulatorAttempt` completed fields; enum checks | `apps/literacy/models.py:ck_scenario_scam_has_tactic`, `ck_flag_w_pct_range`, `ck_attempt_completed_fields` | Implemented |
| **D17** | `ck_attempt_scenario_count` (cardinality = 5); `ck_answer_flag_only_if_scam`; `ScenarioTactic` = `Tactic.values` + "NONE"; `started_at` timezone.now | `apps/literacy/models.py:ck_attempt_scenario_count`, `ck_answer_flag_only_if_scam` | Implemented |
| **D18** | `ck_rule_pattern_lowercase`; `ck_rule_pattern_not_blank`; `ScannerConfig` boundary checks; `ScanResult` array check; `SystemAuditLog` metadata object check | `apps/scanner/models.py:ck_rule_pattern_lowercase`, `ck_config_singleton`, `ck_scan_breakdown_is_array`, `apps/ops/models.py:ck_audit_target_pair` | Implemented |
| **D19** | `ScannerConfig` singleton (`id=1`, `ruleset_version=1`) seeded via migration `0002_seed_scanner_config`; default rules deferred to Phase 5 | migration `scanner/0002_seed_scanner_config.py` | Implemented |
| **D20** | Permanent schema inventory safety-net test (`apps/core/tests/test_schema_inventory.py`) asserting exact 25 public tables, no duplicate indkeys, exact constraints/indexes | `apps/core/tests/test_schema_inventory.py` | Implemented |
| **D21** | `docs/erd.md` generated from live Django models via `backend/tools/generate_erd.py` | `backend/tools/generate_erd.py`, `docs/erd.md` | Implemented |
| **D22** | Fixed-length `char(n)` columns in 03a implemented as `varchar(n)` because Django has no fixed-length type. Affected: `currency(3)`, `country_code(2)`, `sha256(64)`, `endpoint_hash(64)`, `unsubscribe_token_hash(64)`, `actor_ip_hash(64)`, `language(2)`. Exact lengths enforced by services/validators | `apps/reports/models.py`, `apps/alerts/models.py`, `apps/ops/models.py`, `apps/literacy/models.py` | Implemented |
| **D23** | `public_note` (`intel_verifiedindicator`) and `alt_text` (`literacy_guideasset`) are `NOT NULL` with empty-string default; DB has no column defaults because Django applies defaults in Python | `apps/intel/models.py:public_note`, `apps/literacy/models.py:alt_text`, migrations `intel/0001_initial.py`, `literacy/0001_initial.py` | Implemented |

## Standing rules for model tasks
- Index names max 30 characters; check every name.
- Explicit constraint names; CheckConstraint uses condition=.
- Do not add defaults, nullability, or constraints that 03a does not state. Propose extras in the plan; do not implement them without approval.
- Failing-insert tests: inside transaction.atomic(), inside pytest.raises(IntegrityError), assert the constraint or column name appears in the error, with a positive control. Add boundary-pass tests for every limit. Add on_delete tests (PROTECT raises ProtectedError, SET_NULL nulls the column).
- When an explicit index covers a FK column, set db_index=False on the FK (no duplicate indexes). Check this in sqlmigrate.
- Cross-app FKs use string references and a clean migration order; show the dependencies blocks.
- Any test using transaction=True must also use serialized_rollback=True so migration-seeded rows survive.
- Proof list: ruff, plain pytest -q, makemigrations --check --dry-run, showmigrations, FULL sqlmigrate for each new migration, git status --short. Never commit without my OK.

## Deferred
- **Audit log append-only trigger (Phase 11):** Must allow an UPDATE that only sets `actor_id` to NULL (Django SET_NULL on user delete), allow DELETE only in the retention purge, and ideally use a separate DB role.
- **Default heuristic rules command (Phase 5):** Management command `seed_default_rules` requiring an existing admin user to author the initial ruleset (cannot run in data migration without an admin user).
- **Frontend build plan:** Blocked until the frontend requirements and UI design specification document is drafted.
- **GitHub remote repository setup:** Configure git remote origin when the remote repository is created by the owner.

## Open questions for the owner
- (none yet)

## Known issues
- (none yet)

## Commands that work right now
- Start DB: `docker compose up -d db`
- Migrate: `cd backend; python manage.py migrate`
- Run tests: `cd backend; pytest -q`
- Run lint: `cd backend; ruff check .`
- Dump schema: `cd backend; python tools/dump_schema.py`
- Generate ERD: `cd backend; python tools/generate_erd.py`
