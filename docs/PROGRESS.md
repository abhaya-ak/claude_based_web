# PROGRESS (the agent reads this at session start and updates it at the end of every task)

## Current phase
Phase 3 — Accounts, authentication, RBAC (planning)

## Status
| Phase | Owner | Status | Commit/PR | Notes |
|---|---|---|---|---|
| 0 Governance | all | done | 34a26cf | Task 0 done; repo setup, rules, contracts frozen |
| 1A DB design review | all | done | 34a26cf | Design frozen, contracts merged |
| 1B Models + migrations | all | done, merge pending | | 19 app tables, 168 tests, ERD + schema inventory gate complete |
| 2 Scaffold | S4 | todo | | |
| 3 Auth/RBAC | S4 | in_progress | | Planning Phase 3 |
| 3.1 Foundation | S4 | done | | Token blacklist, ops 0002 (18 audit types), JWT/cookie, permissions, throttles |
| 3.2 Public auth | S4 | done | | register, register/staff, login, refresh, logout |
| 3.3 Authenticated | S4 | todo | | me, password/change |
| 3.4 Admin portal | S4 | todo | | list, approve, reject, change-role |
| 3.5 Commands & jobs | S4 | todo | | create_admin, run_jobs (advisory lock) |
| 3.6 Closing | S4 | todo | | Route-walk, RBAC matrix, OpenAPI, docs, gate |
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
| **D41** | Lift Phase 2 scope guard for `rest_framework_simplejwt.token_blacklist`; add 2 tables (`token_blacklist_outstandingtoken`, `token_blacklist_blacklistedtoken`) to schema inventory (27 tables total); preserve duplicate-index check; record in 03a §13 | Phase 3 plan, `docs/PROGRESS.md` | Approved |
| **D42** | Migration `ops 0002` adds 3 audit event types (`USER_REGISTERED`, `ROLE_CHANGED`, `PASSWORD_CHANGED`); `ck_audit_event_type` updated to 18 allowed values; update `AuditEventType` enum, 03a §2 and §4.19; verify via sqlmigrate | Phase 3 plan, `docs/PROGRESS.md` | Approved |
| **D43** | Refresh cookie: name `refresh`, HttpOnly, SameSite=Lax, Path=/api/v1/auth/, Max-Age 7 days; `REFRESH_COOKIE_SECURE` setting (dev False, prod True fail-fast); access token returned only in JSON body | `docs/02-project-architecture.md` §5.1, Phase 3 plan | Approved |
| **D44** | `/auth/refresh/` and `/auth/logout/` read refresh token from cookie only (never body) and require `X-Requested-With: scamshield-web` header (missing → 403 `permission_denied`) | Phase 3 plan, `docs/PROGRESS.md` | Approved |
| **D45** | Login: lower-cased email lookup; identical 401 `authentication_failed` message for unknown email, wrong password, inactive user; dummy password check on unknown email to resist timing attacks; unapproved staff returns 403 `account_not_approved` with no tokens; success returns `{access, user}` and sets cookie; audit `LOGIN_SUCCESS` and `LOGIN_FAILURE` (ip hash + target `("USER", user_id)` when user exists, never email) | `docs/03-backend-build-plan.md` Phase 3, Phase 3 plan | Approved |
| **D46** | Registration: `POST /auth/register/` creates `CITIZEN` only (ignores payload `role`), returns 201 with user and no tokens; `POST /auth/register/staff/` accepts role in `{ANALYST, EDUCATOR}` only, requires `organization` and `credential_note` (max 1000 chars), sets `approval_status=PENDING`, returns 201 with message and no tokens; duplicate email returns 409 `conflict`; audit `USER_REGISTERED` / `STAFF_REGISTERED` | `docs/03-backend-build-plan.md` Phase 3, Phase 3 plan | Approved |
| **D47** | Throttling from audit table: login failures max 10/ip_hash/15m and max 10/target account/15m; registrations max 10/ip_hash/1h; exceeding limit returns 429 `throttled` with `Retry-After` header and writes `RATE_LIMIT_BLOCK` audit row | `docs/02-project-architecture.md` §16 R-C6, Phase 3 plan | Approved |
| **D48** | Passwords: min length 10 + Django common-password, numeric, and user-attribute validators; `POST /auth/password/change/` requires current password, blacklists all outstanding refresh tokens for that user, clears cookie, returns 204, audits `PASSWORD_CHANGED` | `docs/02-project-architecture.md` §5.2, Phase 3 plan | Approved |
| **D49** | No custom claims in JWT; authorization reads role/approval from DB user; `SIMPLE_JWT` with `JWT_SIGNING_KEY`, HS256, access 15m, refresh 7d, rotation + blacklist enabled; prove UUID user id works in tokens (TO BE PROVEN) | `docs/03-backend-build-plan.md` Phase 3, Phase 3 plan | Approved |
| **D50** | Admin rules: only `PENDING` staff can be approved or rejected (409 conflict otherwise); reject requires reason; approve sets `approved_by` and `approved_at`; admin cannot change own role; last active `ADMIN` cannot be demoted or deactivated; role change allowed in `{CITIZEN, ANALYST, EDUCATOR, ADMIN}`; audited via `ROLE_APPROVED`, `ROLE_REJECTED`, `ROLE_CHANGED` | `docs/03-backend-build-plan.md` Phase 3, Phase 3 plan | Approved |
| **D51** | Idempotent `create_admin` command (password from `ADMIN_PASSWORD` env or interactive prompt, role `ADMIN`, `APPROVED`); `run_jobs` command with job registry, each job acquiring Postgres advisory lock (`pg_try_advisory_lock`) to skip concurrent runs; initial job: flush expired JWT tokens | `docs/02-project-architecture.md` §14, `docs/03-backend-build-plan.md` Phase 3 | Approved |
| **D52** | Phase 3 API inventory: auth (`register`, `register/staff`, `login`, `refresh`, `logout`, `me`, `password/change`); admin (`GET /admin-portal/users/?status=`, `POST /admin-portal/users/{id}/approve/`, `/reject/`, `/change-role/`); add change-role to `docs/02-project-architecture.md` §6; explicit permission classes (`AllowAny` on public endpoints); explicit serializer field lists with no password hash exposed | `docs/02-project-architecture.md` §6, Phase 3 plan | Approved |

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
