# PROGRESS (the agent reads this at session start and updates it at the end of every task)

## Current phase
Phase 1B — Models + migrations

## Status
| Phase | Owner | Status | Commit/PR | Notes |
|---|---|---|---|---|
| 0 Governance | all | done | 34a26cf | Task 0 done; repo setup, rules, contracts frozen |
| 1A DB design review | all | done | 34a26cf | Design frozen, contracts merged |
| 1B Models + migrations | all | in progress | | Task 1 (accounts.User) done |
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

## Open questions for the owner
- (none yet)

## Known issues
- (none yet)

## Commands that work right now
- Start DB: `docker compose up -d db`
- Migrate: `cd backend; python manage.py migrate`
- Run tests: `cd backend; pytest -q`
- Run lint: `cd backend; ruff check .`
