# PROGRESS (the agent reads this at session start and updates it at the end of every task)

## Current phase
Phase 1B — Models + migrations

## Status
| Phase | Owner | Status | Commit/PR | Notes |
|---|---|---|---|---|
| 0 Governance | all | done | 34a26cf | Task 0 done; repo setup, rules, contracts frozen |
| 1A DB design review | all | done | 34a26cf | Design frozen, contracts merged |
| 1B Models + migrations | all | in progress | | Tasks 1 (accounts), 2 (reports), 3 (intel) done |
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

## Decisions made (do not revisit without owner approval)
- **D1 (Indicators limit):** The "max 5 indicators" limit applies strictly to user-submitted indicators. Auto-derived `DOMAIN` rows do not count (max 10 total indicator rows per report). Enforced in the service/serializer, not in the database.
- **D2 (Indicator HMAC key & PII separation):** Dedicated secret `INDICATOR_HMAC_KEY` used only to hash `BANK_ACCOUNT` values (not rotated casually). `HMAC_IP_SALT` is used exclusively for IP hashes and may rotate per policy. `raw_value` is retained to permit future re-hash migrations.
- **D3 (Scanner point defaults):** In FR-4.1.3 (docs/01), scanner point values and thresholds are defaults editable by admin via rule weights and scanner config (`SCANNER_CONFIG`); the heuristic scoring formula structure is fixed.
- **D4 (Unified AudienceGroup enum):** Replaced separate `TargetGroup` and `Audience` enums with a single shared `AudienceGroup` enum (`GENERAL`, `ELDERLY`, `TEENAGER`, `NON_TECH`) across alerts, advisories, and educational guides. Advisories additionally permit `ALL`. UI display label for `ELDERLY`: "Seniors & family".
- **D5 (Bank account normalisation):** Bank account normalization removes spaces, dashes, and dots; keeps digits only, preserving leading zeros; applies no bank-specific format rules (documented known limitation).
- **D6 (Upload path & SMS flag):** Evidence upload remains server-side for now; the Phase 12 load test will evaluate server load and decide whether to switch to pre-signed direct S3 uploads. SMS alerting remains behind a feature flag, OFF by default.
- **D7 (Email uniqueness & lowercasing):** `email` has `unique=True` on the model field AND a functional `UniqueConstraint` on `Lower("email")` (named `uq_user_email_lower`); `UserManager` lowercases email on create. Django requires `USERNAME_FIELD` to be unique.
- **D8 (Python 3.13 everywhere):** Standardized on Python 3.13 across developer environments, Docker base images (`python:3.13-slim`), and runtime configurations.
- **D9 (Deferred verified_indicator FK):** ReportIndicator.verified_indicator is NOT created in the reports app yet; a later reports migration adds it after the intel app exists.
- **D10 (Index name truncation):** Truncated `idx_report_platform_cat_created` (31 chars) to `idx_report_plat_cat_created` (27 chars) to satisfy Django's 30-character index name limit.
- **D11 (Shared AudienceGroup enum & ScamCategory import):** The shared enum `AudienceGroup` (`GENERAL`, `ELDERLY`, `TEENAGER`, `NON_TECH`) lives in `apps/core/enums.py`. `alerts`, `broadcasts`, and `literacy` import it. `ScamCategory` is imported from `apps.reports.models`.
- **D12 (ThreatAdvisory.published_by FK on_delete):** `ThreatAdvisory.published_by` is a nullable FK with `on_delete=models.PROTECT`, like the other staff FKs (03a section 1).
- **D13 (Categories array containment constraint):** Added check constraint `ck_sub_categories_elements` on `AlertSubscription` enforcing `categories <@ ARRAY[... valid ScamCategory values ...]` (where empty array `[]` represents all categories).
- **D14 (Array element CHECKs & Guide enum validations):** Array elements for `audience_groups` must be contained by `AudienceGroup.values` from `apps.core.enums`; `tactics` must be contained by `[URGENCY, AUTHORITY, FEAR, GREED]`. Explicit CHECK constraints enforce valid choices for `language` (`en`, `ne`, `ms`), `readability_mode` (`STANDARD`, `LARGE_HIGH_CONTRAST`), `status` (`DRAFT`, `PUBLISHED`, `ARCHIVED`), and `asset_type` (`PDF`, `AUDIO`, `IMAGE`). `GuideAsset` of type `IMAGE` requires non-empty trimmed `alt_text` (`Length(Trim(alt_text)) >= 1`).
- **D15 (EducationalGuide & GuideAsset business rules):** Added three explicit constraints: (1) `ck_guide_published_audience`: if `status = 'PUBLISHED'` then `CARDINALITY(audience_groups) >= 1`; (2) `ck_guide_published_timestamp`: if `status = 'PUBLISHED'` then `published_at IS NOT NULL`; (3) `ck_asset_duration_positive`: `duration_seconds IS NULL OR duration_seconds > 0`.
- **D16 (Simulator models business rules and constraints):** Added explicit constraints across simulator tables: (1) `ck_scenario_scam_has_tactic`: a scam scenario must have `tactic <> 'NONE'`; (2) `ScenarioRedFlag`: `w_pct > 0` and `h_pct > 0` (`ck_flag_w_pct_range`, `ck_flag_h_pct_range`); (3) `SimulatorAttempt`: status `COMPLETED` requires `completed_at NOT NULL` and `score_pct NOT NULL` (`ck_attempt_completed_fields`); (4) Enum CHECKs for channel, tactic (`URGENCY`, `AUTHORITY`, `FEAR`, `GREED`, `NONE`), scenario status, flag_code (9 codes), and attempt status; (5) `AttemptAnswer.selected_flag_code` is NULL or a valid `RedFlagCode`.
- **D17 (Simulator scenario count and answer scam flag constraints):** (1) `ck_attempt_scenario_count`: `CARDINALITY(scenario_ids) = 5` enforced in the database using `Func("scenario_ids", function="CARDINALITY")`; (2) `ck_answer_flag_only_if_scam`: `answered_is_scam = TRUE OR selected_flag_code IS NULL` on `AttemptAnswer`; (3) `SimulatorAttempt.started_at` uses `default=timezone.now` in Django (no DB default).
- **D18 (Scanner and Ops models integrity rules and constraints):** Added explicit constraints: (1) `ck_rule_pattern_lowercase`: `pattern = LOWER(pattern)`; (2) `ck_rule_pattern_not_blank`: `LENGTH(TRIM(pattern)) >= 1`; (3) `ScannerConfig`: all four point/threshold fields between 0 and 100 (`threshold` between 1 and 100), `ruleset_version >= 1`. `ScannerConfig.id` keeps singleton CHECK `id = 1`; (4) `ScanResult.breakdown` must be a JSON array (`jsonb_typeof = 'array'`); (5) `SystemAuditLog.metadata` must be a JSON object (`jsonb_typeof = 'object'`), default=dict; (6) `SystemAuditLog`: `target_type` and `target_id` are both NULL or both set (`ck_audit_target_pair`); (7) CHECKs for `rule_type`, `event_type` (15 values), `severity`.
- **D19 (ScannerConfig singleton data migration & unseeded rules):** The `ScannerConfig` row (`id=1`, `ruleset_version=1`, all defaults) is created by an idempotent data migration (`scanner 0002_seed_scanner_config`). Default heuristic rules are NOT seeded at migration time (since `HeuristicRule.created_by` is a required PROTECT FK and no admin user exists during migration); they will be seeded by a management command in Phase 5.

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
- Audit log append-only trigger (Phase 11). It must allow an UPDATE that only sets actor_id to NULL (Django SET_NULL on user delete), allow DELETE only in the retention purge, and ideally use a separate DB role.

## Open questions for the owner
- (none yet)

## Known issues
- (none yet)

## Commands that work right now
- Start DB: `docker compose up -d db`
- Migrate: `cd backend; python manage.py migrate`
- Run tests: `cd backend; pytest -q`
- Run lint: `cd backend; ruff check .`
