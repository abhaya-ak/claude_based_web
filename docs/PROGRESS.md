# PROGRESS (the agent reads this at session start and updates it at the end of every task)

## Current phase
Phase 2 — Project scaffold and foundations

## Status
| Phase | Owner | Status | Commit/PR | Notes |
|---|---|---|---|---|
| 0 Governance | all | done | 34a26cf | Task 0 done; repo setup, rules, contracts frozen |
| 1A DB design review | all | done | 34a26cf | Design frozen, contracts merged |
| 1B Models + migrations | all | done, merge pending | | 19 app tables, 168 tests, ERD + schema inventory gate complete |
| 2 Scaffold | S4 | in progress | | Phase 2 foundations |
| ├─ 2.1 Settings & test safety | S4 | done | | Settings split (base/dev/test/prod), root URLs, JSON handlers, .env.example, AWS test safety fixture (35 new tests) |
| ├─ 2.2 Error envelope & logging | S4 | done | | Error envelope, pagination, request ID ContextVar/middleware, PII scrubber, access log (35 new tests) |
| ├─ 2.3 Health & client IP | S4 | done | | HealthCheckMiddleware (first), liveness/readiness endpoints, client IP & HMAC hashing (12 new tests) |
| ├─ 2.4 AWS, metrics & audit | S4 | done | | AWS client factory (timeouts/caching), metrics emitter, audit log_event with lazy ops model import (26 new tests) |
| ├─ 2.5 OpenAPI schema | S4 | done | | drf-spectacular, committed backend/openapi.yaml, drift check, docs UI disabled in prod (4 new tests) |
| ├─ 2.6 Containerization | S4 | done | | Multi-stage Dockerfile (python:3.13-slim, non-root, libmagic1), gunicorn entrypoint no access log, health & non-root proof |
| └─ 2.7 CI & closing gate | S4 | todo | | GitHub Actions CI, pre-commit, deployment checks, Phase 2 gate |
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
| **D24** | Daily work stays in venv (PowerShell). Docker runs DB; backend container proves production image boots and passes healthcheck. Both paths documented in PROGRESS | Phase 2 planning | Approved |
| **D25** | Scope guard: Phase 2 creates NO models and NO migrations. Schema inventory test stays green (25 tables). `makemigrations --check` stays clean. Contrib apps stay pinned | Phase 2 planning | Approved |
| **D26** | Error envelope for non-2xx: `{"error":{"code","message","details","request_id"}}`. Handlers for 400, 401, 403, 404, 405, 409, 429 (Retry-After), 500 (no stack trace leak). Root URL handlers for non-DRF errors | Phase 2 planning, `docs/02-project-architecture.md` §4 | Approved |
| **D27** | Request ID: incoming `X-Request-ID` validated against `^[A-Za-z0-9._-]{8,64}$`, else generate uuid4 hex. Returned as `X-Request-ID`. ContextVar for logs, errors, audit | Phase 2 planning | Approved |
| **D28** | JSON logging to stdout via `python-json-logger`. PII scrubber filter masks 16 forbidden keys anywhere in log record. Single-line access log (NO query string, bodies, or headers) | Phase 2 planning, `docs/02-project-architecture.md` §15 | Approved |
| **D29** | Health endpoints: `/api/v1/health/` liveness (`{"status":"ok"}`); `/api/v1/health/ready/` readiness (`SELECT 1`, 2s timeout; 200 or 503). `HealthCheckMiddleware` is FIRST in MIDDLEWARE, answers before host validation (R-D4) | Phase 2 planning, `docs/02-project-architecture.md` R-D4 | Approved |
| **D30** | Client IP: `TRUSTED_PROXY_HOPS` setting (dev/test 0, prod required). Client IP = `XFF[-(N+1)]` with `REMOTE_ADDR` fallback; validated via `ipaddress`. `core.ip.client_ip_hash(request)` is 64 hex chars | Phase 2 planning, `docs/02-project-architecture.md` R-C7 | Approved |
| **D31** | AWS client factory: `core.aws.client(service)` with connect_timeout=2s, read_timeout=5s, max_attempts=2, region from `AWS_REGION`, optional `AWS_ENDPOINT_URL`, thread-safe cache, `reset_clients()`. Test autouse fixture blocks real AWS | Phase 2 planning, `docs/contracts.md` §3.4 | Approved |
| **D32** | Metrics: `core.metrics.emit` never raises. Allowed metric names (7) and dimensions (Environment, Platform). `METRICS_ENABLED` switches CloudWatch PutMetricData in `ScamShield/Operations` | Phase 2 planning, `docs/contracts.md` §3.2 | Approved |
| **D33** | Audit writer: `core.audit.log_event` implemented in Phase 2. Validates event_type and severity against ops enums; raises ValueError on scrubbed keys; fills request_id; writes in caller's transaction | Phase 2 planning, `docs/contracts.md` §3.1 | Approved |
| **D34** | Pagination: `StandardPagination`, limit/offset, default 20, max 100, response `{count, next, previous, results}` | Phase 2 planning, `docs/02-project-architecture.md` §4 | Approved |
| **D35** | Settings split `base/dev/test/prod`. Prod fails fast on missing/invalid secrets, hosts, hops, or DEBUG=True. DB: `CONN_MAX_AGE=60`, `statement_timeout=10000`, `sslmode=require`. JSON-only renderer. Admin uninstalled | Phase 2 planning, `docs/02-project-architecture.md` §12, R-A1 | Approved |
| **D36** | Deploy checks: silence ONLY `security.W004` and `security.W008` in `SILENCED_SYSTEM_CHECKS` citing R-D5 (CloudFront handles HTTPS/HSTS). All other checks pass with `--fail-level WARNING` | Phase 2 planning, `docs/02-project-architecture.md` R-D5 | Approved |
| **D37** | Gunicorn: no access log (avoids logging query strings); error log to stdout; flags per 02 §13. Docs 02 §13 updated. API docs/schema UI disabled in prod | Phase 2 planning, `docs/02-project-architecture.md` §13 | Approved |
| **D38** | `APPEND_SLASH=False`; every route ends with a slash | Phase 2 planning | Approved |
| **D39** | Hash-pinned lock files deferred to Phase 13 (Linux build). Dependencies unchanged in Phase 2 | Phase 2 planning | Approved |
| **D40** | Phase 2 adjustments (tasks 2.2-2.5): `openapi.yaml` located at `backend/openapi.yaml` (regenerated via `manage.py spectacular --file openapi.yaml --validate`); `ProtectedSpectacular*View` classes for dynamic runtime `ENABLE_API_DOCS` toggle; `ErrorResponse` schema component via `SPECTACULAR_SETTINGS["APPEND_COMPONENTS"]`; typed `@extend_schema` on health views | Phase 2 task 2.5b | Implemented |

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
- **Hash-pinned lock files (D39, Phase 13):** Exact sha256 hash pinning of dependency lock files deferred to Linux container build phase.

## Open questions for the owner
- (none yet)

## Known issues
- (none yet)

## Commands that work right now
- Start DB: `docker compose up -d db`
- Migrate: `cd backend; python manage.py migrate`
- Run tests: `cd backend; pytest -q`
- Run lint: `cd backend; ruff check .`
- Regenerate OpenAPI: `cd backend; python manage.py spectacular --file openapi.yaml --validate`
- Dump schema: `cd backend; python tools/dump_schema.py`
- Generate ERD: `cd backend; python tools/generate_erd.py`
