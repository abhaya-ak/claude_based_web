# ScamShield Cloud — Database Design (Schema, ERD, DB Architecture)

Related: `01-project-overview.md` · `02-project-architecture.md` · `03-backend-build-plan.md`
**Gate:** no backend code is written until the team has reviewed and frozen this document (Phase 1 of the build plan).

---

## 1. Design principles and conventions

| Topic | Rule |
|---|---|
| Engine | PostgreSQL 16 (RDS). Schema owned by **Django models + migrations** (not Prisma) |
| Primary keys | `uuid` (v4) for anything exposed in URLs/APIs; `bigint` identity for internal high-volume rows |
| Time | `timestamptz`, stored UTC (`USE_TZ=True`); `created_at` / `updated_at` on mutable tables via abstract `TimeStampedModel` |
| Enums | Django `TextChoices` stored as `varchar` + DB `CHECK` constraint (easier to migrate than native PG enums) |
| Arrays / JSON | `varchar[]` (with GIN index) for small tag sets; `jsonb` for flexible breakdowns |
| Integrity | Constraints in the DB (unique, check, FK), not only in serializers |
| Naming | Django default table names `app_model`; explicit index names `idx_<table>_<cols>` |
| Deletes | Staff FKs `PROTECT` (deactivate users, don't delete); citizen-linked FKs `SET_NULL`; children of a report `CASCADE`; content referenced by history is **archived**, not deleted |
| Money | `numeric(12,2)` + ISO currency code; never float |
| PII | Minimised; classified in Section 8; anonymous reports have no user link |

## 2. Enum catalogue (frozen contract)

| Enum | Values |
|---|---|
| Role | `CITIZEN`, `ANALYST`, `EDUCATOR`, `ADMIN` |
| ApprovalStatus | `APPROVED`, `PENDING`, `REJECTED` |
| ScamCategory | `PHISHING`, `FAKE_JOB`, `ECOMMERCE_FRAUD`, `IMPERSONATION`, `OTHER` |
| Platform | `WHATSAPP`, `TELEGRAM`, `FACEBOOK`, `EMAIL`, `SMS`, `WEBSITE`, `OTHER` |
| IndicatorType | `PHONE`, `URL`, `DOMAIN`, `EMAIL`, `BANK_ACCOUNT` |
| PaymentMethod | `NONE`, `BANK_TRANSFER`, `E_WALLET`, `CARD`, `CRYPTO`, `CASH`, `OTHER` |
| ReportStatus | `PENDING`, `VERIFIED`, `REJECTED` |
| ScanStatus | `PENDING`, `DONE`, `FAILED` |
| ThreatLevel | `MEDIUM` (1–2 reports), `HIGH` (3–9), `CRITICAL` (10+) |
| IndicatorStatus | `ACTIVE`, `REVOKED` |
| TriageAction | `VERIFY`, `REJECT` |
| AudienceGroup | `GENERAL`, `ELDERLY`, `TEENAGER`, `NON_TECH` (shared across alerts, advisories, guides; UI label for `ELDERLY`: "Seniors & family"; advisories additionally allow `ALL`) |
| Channel | `EMAIL`, `SMS` |
| SubscriptionStatus | `PENDING_CONFIRMATION`, `ACTIVE`, `UNSUBSCRIBED`, `FAILED` |
| AdvisorySeverity / Status | `INFO`,`WARNING`,`CRITICAL` / `DRAFT`,`PUBLISHED`,`FAILED` |
| Tactic | `URGENCY`, `AUTHORITY`, `FEAR`, `GREED` (+ `NONE` on scenarios) |
| Language | `en`, `ne`, `ms` |
| ReadabilityMode | `STANDARD`, `LARGE_HIGH_CONTRAST` |
| ContentStatus (guide) | `DRAFT`, `PUBLISHED`, `ARCHIVED` |
| ScenarioStatus | `DRAFT`, `PUBLISHED`, `ARCHIVED` |
| ScenarioChannel | `SMS`, `EMAIL`, `WHATSAPP`, `WEBSITE`, `SOCIAL` |
| AssetType | `PDF`, `AUDIO`, `IMAGE` |
| RedFlagCode | `MISMATCHED_DOMAIN`, `ARTIFICIAL_URGENCY`, `AUTHORITY_IMPERSONATION`, `THREAT_OF_LOSS`, `TOO_GOOD_TO_BE_TRUE`, `REQUEST_FOR_SENSITIVE_DATA`, `SUSPICIOUS_LINK`, `POOR_GRAMMAR`, `OTHER` |
| RuleType | `KEYWORD`, `TLD`, `SHORTENER` |
| AttemptStatus | `IN_PROGRESS`, `COMPLETED` |
| AuditSeverity | `INFO`, `WARN`, `ALERT` |

## 3. Entity-relationship diagram

The entity-relationship diagram is generated directly from the live Django models via `backend/tools/generate_erd.py`.
See the full visual diagram and complete table definitions in [docs/erd.md](erd.md).

## 4. Table specifications

### 4.1 `accounts_user` (S4 owns; shared)
| Column | Type | Constraints / notes |
|---|---|---|
| id | uuid | PK |
| email | varchar(254) | login; **unique on `lower(email)`** |
| password | varchar(128) | Argon2 hash |
| full_name | varchar(150) | |
| role | varchar(10) | CHECK in Role; default `CITIZEN` |
| approval_status | varchar(10) | CHECK; `APPROVED` for citizens, `PENDING` for staff sign-ups |
| organization | varchar(200) | null; required for staff sign-up |
| credential_note | text | null; staff justification (≤ 1000 chars) |
| approved_by_id | uuid | FK → user, null, SET_NULL |
| approved_at | timestamptz | null |
| rejection_reason | varchar(300) | null |
| is_active | boolean | default true |
| is_superuser | boolean | default false (Django auth requirement; Django admin disabled in prod) |
| last_login | timestamptz | null |
| created_at / updated_at | timestamptz | |
CHECK: `role = 'CITIZEN' → approval_status = 'APPROVED'`.

### 4.2 `reports_scamreport` (S1)
| Column | Type | Constraints / notes |
|---|---|---|
| id | uuid | PK |
| reference_code | varchar(24) | UNIQUE; `SCM-<year>-<8 random base32>` |
| client_submission_id | uuid | UNIQUE, null; idempotency key |
| reporter_id | uuid | FK → user, null, SET_NULL |
| is_anonymous | boolean | CHECK `NOT (is_anonymous AND reporter_id IS NOT NULL)` |
| access_key_hash | varchar(128) | null; only for anonymous reports |
| category | varchar(20) | CHECK ScamCategory |
| platform | varchar(12) | CHECK Platform |
| message_text | text | ≤ 5000 chars (CHECK `char_length ≤ 5000`) |
| financial_loss | numeric(12,2) | default 0, CHECK ≥ 0 |
| currency | char(3) | ISO 4217 (MYR, NPR, USD…) |
| payment_method | varchar(15) | default `NONE` |
| country_code | char(2) | ISO 3166-1 alpha-2 |
| admin_area | varchar(100) | null; from an allow-list (state/province) |
| incident_date | date | null |
| status | varchar(10) | default `PENDING` |
| risk_score | smallint | null; CHECK 0–100 (denormalised from `scan_result`, single writer = scan callback) |
| is_high_priority | boolean | default false |
| scan_status | varchar(10) | default `PENDING` |
| scan_attempts | smallint | default 0 |
| scan_dispatched_at | timestamptz | null |
| reviewed_by_id | uuid | FK → user, null, SET_NULL |
| reviewed_at | timestamptz | null |
| review_note | varchar(500) | null |
| created_at / updated_at | timestamptz | |

### 4.3 `reports_reportindicator` (S1)
| Column | Type | Constraints / notes |
|---|---|---|
| id | bigint | PK identity |
| report_id | uuid | FK → report, CASCADE |
| type | varchar(12) | CHECK IndicatorType |
| raw_value | varchar(512) | as submitted (analyst-only exposure; kept so re-hash migration is possible if INDICATOR_HMAC_KEY changes) |
| normalized_value | varchar(512) | E.164 / canonical URL / lower-case domain / lower-case email / **HMAC-SHA256 hex for BANK_ACCOUNT** using dedicated `INDICATOR_HMAC_KEY` (normalisation: remove spaces, dashes, dots; keep digits only, preserving leading zeros; no bank-specific rules — documented known limitation) |
| display_value | varchar(128) | masked for public use (`+60•••••789`, `lazada-p••••.xyz`) |
| verified_indicator_id | uuid | FK → verified_indicator, null, SET_NULL |
| created_at | timestamptz | |
UNIQUE `(report_id, type, normalized_value)`.
A URL submission also creates a `DOMAIN` row (registrable domain extracted offline with `tldextract`). User-submitted indicators are capped at 5; auto-derived `DOMAIN` rows do not count toward this limit (max 10 total indicator rows per report, enforced in service/serializer, not in DB per D1).

### 4.4 `reports_reportevidence` (S1)
| Column | Type | Constraints / notes |
|---|---|---|
| id | uuid | PK |
| report_id | uuid | FK CASCADE |
| s3_key | varchar(300) | UNIQUE; `evidence/{report_id}/{uuid}.{ext}` |
| content_type | varchar(40) | `image/png`, `image/jpeg`, `application/pdf` (CHECK) |
| size_bytes | integer | CHECK 1..5242880 |
| sha256 | char(64) | integrity / duplicate-evidence detection |
| created_at | timestamptz | |
Max 3 per report (enforced in service + test).

### 4.5 `reports_recoveryplaybook` (S1, reference data)
| Column | Type | Notes |
|---|---|---|
| id | bigint | PK |
| category / payment_method / country_code | varchar | null = "any" |
| title | varchar(150) | |
| steps | jsonb | ordered `[{"title","detail"}]` |
| hotlines | jsonb | `[{"name","number","url"}]` — **verify numbers from official sources before seeding** |
| priority | smallint | more specific rule wins; ties by priority |
| is_active | boolean | |
| updated_at | timestamptz | |

### 4.6 `intel_verifiedindicator` (S2)
| Column | Type | Constraints / notes |
|---|---|---|
| id | uuid | PK |
| type | varchar(12) | CHECK IndicatorType |
| normalized_value | varchar(512) | |
| display_value | varchar(128) | masked, public |
| primary_category | varchar(20) | most frequent category among linked reports |
| threat_level | varchar(10) | `MEDIUM` / `HIGH` / `CRITICAL` |
| total_report_count | integer | CHECK ≥ 1 |
| first_seen_at / last_seen_at | timestamptz | |
| status | varchar(8) | default `ACTIVE` |
| public_note | varchar(500) | analyst-curated, redacted; shown on Red verdicts |
| verified_by_id | uuid | FK → user, PROTECT |
| verified_at | timestamptz | |
| revoked_by_id / revoked_at / revoke_reason | uuid / timestamptz / varchar(300) | null |
| created_at / updated_at | timestamptz | |
UNIQUE `(type, normalized_value)`.

### 4.7 `intel_triagedecision` (S2)
| Column | Type | Notes |
|---|---|---|
| id | bigint | PK |
| report_id | uuid | FK CASCADE |
| analyst_id | uuid | FK → user, PROTECT |
| action | varchar(8) | `VERIFY` / `REJECT` |
| indicator_id | uuid | FK → verified_indicator, null, SET_NULL |
| reason | varchar(500) | required for `REJECT` |
| created_at | timestamptz | |

### 4.8 `alerts_alertsubscription` (S1)
| Column | Type | Constraints / notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK null SET_NULL |
| channel | varchar(5) | `EMAIL` / `SMS` |
| endpoint | varchar(254) | email or E.164 phone (PII — never logged) |
| endpoint_hash | char(64) | HMAC for uniqueness and lookups |
| audience | varchar(15) | CHECK in `AudienceGroup` (`GENERAL`, `ELDERLY`, `TEENAGER`, `NON_TECH`; UI label for `ELDERLY`: "Seniors & family") |
| categories | varchar(20)[] | empty = all |
| status | varchar(22) | default `PENDING_CONFIRMATION` |
| sns_subscription_arn | varchar(256) | null until SNS returns it |
| unsubscribe_token_hash | char(64) | token emailed/linked; stored hashed |
| created_at / confirmed_at / unsubscribed_at | timestamptz | |
UNIQUE `(channel, endpoint_hash, audience)`.
CHECK `categories <@ ARRAY['PHISHING', 'FAKE_JOB', 'ECOMMERCE_FRAUD', 'IMPERSONATION', 'OTHER']::varchar(20)[]` (empty = all).

### 4.9 `broadcasts_threatadvisory` (S2)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| title | varchar(150) | |
| body | text | ≤ 1500 chars (email body) |
| sms_text | varchar(140) | null; short text for SMS |
| severity | varchar(8) | |
| target_audience | varchar(15) | `ALL` or an `AudienceGroup` |
| category | varchar(20) | null |
| related_indicator_id | uuid | FK null SET_NULL |
| status | varchar(10) | default `DRAFT` |
| sns_message_id | varchar(100) | null |
| created_by_id / published_by_id | uuid | FK → user, PROTECT / null |
| published_at | timestamptz | null |
| created_at / updated_at | timestamptz | |

### 4.10 `literacy_educationalguide` (S3)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| slug | varchar(200) | UNIQUE |
| title | varchar(200) | |
| summary | varchar(500) | |
| body | text | markdown; sanitised when rendered |
| audience_groups | varchar(15)[] | GIN index; `AudienceGroup` values (UI label for `ELDERLY`: "Seniors & family") |
| tactics | varchar(10)[] | GIN index; used for remedial recommendations |
| language | char(2) | default `en` |
| readability_mode | varchar(20) | default `STANDARD` |
| status | varchar(10) | default `DRAFT` |
| author_id | uuid | FK → user, PROTECT |
| published_at | timestamptz | null |
| created_at / updated_at | timestamptz | |
CHECK `language IN ('en', 'ne', 'ms')`.
CHECK `readability_mode IN ('STANDARD', 'LARGE_HIGH_CONTRAST')`.
CHECK `status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')`.
CHECK `audience_groups <@ ARRAY['GENERAL', 'ELDERLY', 'TEENAGER', 'NON_TECH']::varchar(15)[]`.
CHECK `tactics <@ ARRAY['URGENCY', 'AUTHORITY', 'FEAR', 'GREED']::varchar(10)[]`.
CHECK `status != 'PUBLISHED' OR CARDINALITY(audience_groups) >= 1` (`ck_guide_published_audience`).
CHECK `status != 'PUBLISHED' OR published_at IS NOT NULL` (`ck_guide_published_timestamp`).

### 4.11 `literacy_guideasset` (S3)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| guide_id | uuid | FK CASCADE |
| asset_type | varchar(5) | |
| s3_key | varchar(300) | UNIQUE; `guides/{guide_id}/{uuid}.{ext}` |
| content_type | varchar(60) | |
| size_bytes | integer | CHECK > 0 |
| duration_seconds | integer | null (audio) |
| alt_text | varchar(300) | required for `IMAGE` |
| transcript | text | null; recommended for `AUDIO` (accessibility) |
| sort_order | smallint | default 0 |
| created_at | timestamptz | |
CHECK `asset_type IN ('PDF', 'AUDIO', 'IMAGE')`.
CHECK `size_bytes > 0` (`ck_asset_size_bytes_positive`).
CHECK `duration_seconds IS NULL OR duration_seconds > 0` (`ck_asset_duration_positive`).
CHECK `asset_type != 'IMAGE' OR LENGTH(TRIM(alt_text)) >= 1` (`ck_asset_image_alt_text`).

### 4.12 `literacy_simulatorscenario` (S3)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| title | varchar(150) | |
| channel | varchar(10) | |
| is_scam | boolean | |
| tactic | varchar(10) | CHECK `is_scam OR tactic = 'NONE'` |
| image_s3_key | varchar(300) | `scenarios/{uuid}.{ext}` |
| image_alt | varchar(300) | |
| explanation | text | shown after answering |
| difficulty | smallint | CHECK 1..3 |
| status | varchar(10) | default `DRAFT` |
| author_id | uuid | FK PROTECT |
| created_at / updated_at | timestamptz | |
CHECK `channel IN ('SMS', 'EMAIL', 'WHATSAPP', 'WEBSITE', 'SOCIAL')` (`ck_scenario_channel`).
CHECK `tactic IN ('URGENCY', 'AUTHORITY', 'FEAR', 'GREED', 'NONE')` (`ck_scenario_tactic`).
CHECK `status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')` (`ck_scenario_status`).
CHECK `difficulty >= 1 AND difficulty <= 3` (`ck_scenario_difficulty`).
CHECK `is_scam OR tactic = 'NONE'` (`ck_scenario_legit_tactic_none`).
CHECK `NOT is_scam OR tactic <> 'NONE'` (`ck_scenario_scam_has_tactic`).

### 4.13 `literacy_scenarioredflag` (S3)
| Column | Type | Notes |
|---|---|---|
| id | bigint | PK |
| scenario_id | uuid | FK CASCADE |
| flag_code | varchar(30) | CHECK RedFlagCode |
| x_pct, y_pct, w_pct, h_pct | numeric(5,2) | percentages of image size; CHECK 0..100 and `x+w ≤ 100`, `y+h ≤ 100` |
| explanation | varchar(300) | |
CHECK `flag_code IN ('MISMATCHED_DOMAIN', 'ARTIFICIAL_URGENCY', 'AUTHORITY_IMPERSONATION', 'THREAT_OF_LOSS', 'TOO_GOOD_TO_BE_TRUE', 'REQUEST_FOR_SENSITIVE_DATA', 'SUSPICIOUS_LINK', 'POOR_GRAMMAR', 'OTHER')` (`ck_flag_code`).
CHECK `x_pct >= 0 AND x_pct <= 100` (`ck_flag_x_pct_range`).
CHECK `y_pct >= 0 AND y_pct <= 100` (`ck_flag_y_pct_range`).
CHECK `w_pct > 0 AND w_pct <= 100` (`ck_flag_w_pct_range`).
CHECK `h_pct > 0 AND h_pct <= 100` (`ck_flag_h_pct_range`).
CHECK `x_pct + w_pct <= 100` (`ck_flag_x_plus_w_bound`).
CHECK `y_pct + h_pct <= 100` (`ck_flag_y_plus_h_bound`).

### 4.14 `literacy_simulatorattempt` (S3)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK null SET_NULL |
| session_key | uuid | null; anonymous player token generated server-side |
| status | varchar(12) | default `IN_PROGRESS` |
| scenario_ids | uuid[] | the 5 chosen scenarios (server-side random) |
| score_pct | smallint | null; CHECK 0..100 |
| profile | jsonb | null; `{"URGENCY":{"correct":1,"total":2},…}` |
| started_at / completed_at | timestamptz | started_at default timezone.now (Django-side, no DB default) |
CHECK `user_id IS NOT NULL OR session_key IS NOT NULL` (`ck_attempt_user_or_session`).
CHECK `status IN ('IN_PROGRESS', 'COMPLETED')` (`ck_attempt_status`).
CHECK `score_pct IS NULL OR (score_pct >= 0 AND score_pct <= 100)` (`ck_attempt_score_pct_range`).
CHECK `status <> 'COMPLETED' OR (completed_at IS NOT NULL AND score_pct IS NOT NULL)` (`ck_attempt_completed_fields`).
CHECK `CARDINALITY(scenario_ids) = 5` (`ck_attempt_scenario_count`).

### 4.15 `literacy_attemptanswer` (S3)
| Column | Type | Notes |
|---|---|---|
| id | bigint | PK |
| attempt_id | uuid | FK CASCADE |
| scenario_id | uuid | FK → scenario, PROTECT (archive instead of deleting) |
| answered_is_scam | boolean | |
| selected_flag_code | varchar(30) | null |
| is_correct | boolean | computed server-side only |
| created_at | timestamptz | |
UNIQUE `(attempt_id, scenario_id)` (`uq_answer_attempt_scenario`).
CHECK `selected_flag_code IS NULL OR selected_flag_code IN ('MISMATCHED_DOMAIN', 'ARTIFICIAL_URGENCY', 'AUTHORITY_IMPERSONATION', 'THREAT_OF_LOSS', 'TOO_GOOD_TO_BE_TRUE', 'REQUEST_FOR_SENSITIVE_DATA', 'SUSPICIOUS_LINK', 'POOR_GRAMMAR', 'OTHER')` (`ck_answer_selected_flag_code`).
CHECK `answered_is_scam = TRUE OR selected_flag_code IS NULL` (`ck_answer_flag_only_if_scam`).

### 4.16 `scanner_heuristicrule` (S4)
| Column | Type | Notes |
|---|---|---|
| id | bigint | PK |
| rule_type | varchar(10) | `KEYWORD` / `TLD` / `SHORTENER` |
| pattern | varchar(100) | stored lower-case (`urgent`, `.xyz`, `bit.ly`) |
| weight | smallint | CHECK 1..50 (defaults: keyword 15, TLD 25, shortener 15) |
| is_active | boolean | default true |
| created_by_id | uuid | FK PROTECT |
| created_at / updated_at | timestamptz | |
UNIQUE `(rule_type, pattern)` (`uq_rule_type_pattern`).
CHECK `rule_type IN ('KEYWORD', 'TLD', 'SHORTENER')` (`ck_rule_type`).
CHECK `weight >= 1 AND weight <= 50` (`ck_rule_weight_range`).
CHECK `pattern = LOWER(pattern)` (`ck_rule_pattern_lowercase`).
CHECK `LENGTH(TRIM(pattern)) >= 1` (`ck_rule_pattern_not_blank`).

### 4.17 `scanner_scannerconfig` (S4, singleton)
| Column | Type | Notes |
|---|---|---|
| id | smallint | PK, CHECK `id = 1` |
| keyword_cap_points | smallint | default 45 |
| ip_url_points | smallint | default 25 (IP-based URL) |
| prior_pending_points | smallint | default 20 |
| high_priority_threshold | smallint | default 75 |
| ruleset_version | integer | incremented in the same transaction as any rule/config change |
| updated_by_id / updated_at | uuid / timestamptz | |
CHECK `id = 1` (`ck_config_singleton`).
CHECK `ruleset_version >= 1` (`ck_config_ruleset_version`).
CHECK `keyword_cap_points >= 0 AND keyword_cap_points <= 100` (`ck_config_keyword_cap_points`).
CHECK `ip_url_points >= 0 AND ip_url_points <= 100` (`ck_config_ip_url_points`).
CHECK `prior_pending_points >= 0 AND prior_pending_points <= 100` (`ck_config_prior_pending_points`).
CHECK `high_priority_threshold >= 1 AND high_priority_threshold <= 100` (`ck_config_high_priority_threshold`).

### 4.18 `scanner_scanresult` (S4)
| Column | Type | Notes |
|---|---|---|
| id | bigint | PK |
| report_id | uuid | **UNIQUE** FK CASCADE (1-to-1) |
| ruleset_version | integer | |
| risk_score | smallint | CHECK 0..100 |
| breakdown | jsonb | `[{"rule":"urgent","type":"KEYWORD","points":15}, …]` |
| is_high_priority | boolean | |
| lambda_request_id | varchar(64) | null; debugging |
| scanned_at | timestamptz | default timezone.now (Django-side default) |
CHECK `risk_score >= 0 AND risk_score <= 100` (`ck_scan_risk_score_range`).
CHECK `jsonb_typeof(breakdown) = 'array'` (`ck_scan_breakdown_is_array`).

### 4.19 `ops_systemauditlog` (S4)
| Column | Type | Notes |
|---|---|---|
| id | bigint | PK identity |
| occurred_at | timestamptz | default now (Django-side default, no DB default) |
| actor_id | uuid | FK null SET_NULL |
| actor_ip_hash | char(64) | null; salted HMAC of client IP |
| event_type | varchar(40) | see list below |
| severity | varchar(5) | |
| target_type / target_id | varchar(40) / varchar(64) | null |
| metadata | jsonb | small, **no PII** |
| request_id | varchar(64) | null |
Event types: `REPORT_SUBMITTED`, `RATE_LIMIT_BLOCK`, `LOGIN_FAILURE`, `LOGIN_SUCCESS`, `STAFF_REGISTERED`, `ROLE_APPROVED`, `ROLE_REJECTED`, `EVIDENCE_URL_ISSUED`, `INDICATOR_VERIFIED`, `REPORT_REJECTED`, `INDICATOR_REVOKED`, `ADVISORY_PUBLISHED`, `RULE_CHANGED`, `CONFIG_CHANGED`, `SCAN_FAILED`.
CHECK `event_type IN ('REPORT_SUBMITTED', 'RATE_LIMIT_BLOCK', 'LOGIN_FAILURE', 'LOGIN_SUCCESS', 'STAFF_REGISTERED', 'ROLE_APPROVED', 'ROLE_REJECTED', 'EVIDENCE_URL_ISSUED', 'INDICATOR_VERIFIED', 'REPORT_REJECTED', 'INDICATOR_REVOKED', 'ADVISORY_PUBLISHED', 'RULE_CHANGED', 'CONFIG_CHANGED', 'SCAN_FAILED')` (`ck_audit_event_type`).
CHECK `severity IN ('INFO', 'WARN', 'ALERT')` (`ck_audit_severity`).
CHECK `jsonb_typeof(metadata) = 'object'` (`ck_audit_metadata_is_object`).
CHECK `(target_type IS NULL AND target_id IS NULL) OR (target_type IS NOT NULL AND target_id IS NOT NULL)` (`ck_audit_target_pair`).

## 5. Indexes and constraints (beyond PK/UNIQUE above)

| Table | Index | Serves |
|---|---|---|
| scamreport | `idx_report_queue (risk_score DESC NULLS LAST, created_at) WHERE status='PENDING'` | Analyst queue |
| scamreport | `idx_report_status_created (status, created_at DESC)` | Filters/lists |
| scamreport | `idx_report_created (created_at)` | Time-series analytics |
| scamreport | `idx_report_plat_cat_created (platform, category, created_at)` | Volume by platform/category |
| scamreport | `idx_report_geo_created (country_code, admin_area, created_at)` | Losses by region |
| scamreport | `idx_report_reporter (reporter_id, created_at DESC) WHERE reporter_id IS NOT NULL` | "My reports" |
| scamreport | `idx_report_scan_pending (scan_dispatched_at) WHERE scan_status='PENDING'` | Re-dispatch job |
| reportindicator | `idx_ri_type_value (type, normalized_value)` | Lookup, clustering, prior-pending count |
| reportindicator | `idx_ri_verified (verified_indicator_id)` | Join to blacklist |
| verifiedindicator | UNIQUE `(type, normalized_value)` (B-tree) | Public lookup |
| verifiedindicator | `idx_vi_status_level (status, threat_level)`, `idx_vi_last_seen (last_seen_at DESC)` | Analyst lists |
| alertsubscription | `idx_sub_status_audience (status, audience)` | Fan-out checks |
| advisory | `idx_adv_status_published (status, published_at DESC)` | Public advisories page |
| guide | `idx_guide_list (status, language, published_at DESC)`; `idx_guide_audience_gin` (GIN on `audience_groups`); `idx_guide_tactics_gin` (GIN on `tactics`) | Hub filters, remedial lookups |
| scenario | `idx_scn_status (status)` | Random selection |
| attempt | `idx_attempt_user (user_id, started_at DESC)` | History |
| auditlog | `idx_audit_rate (event_type, actor_ip_hash, occurred_at DESC)`; `idx_audit_time (occurred_at)`; `idx_audit_actor (actor_id, occurred_at DESC)` | Rate limiting, viewer, retention purge |

## 6. Key query patterns (design checks)

| Use case | Query shape | Expected plan |
|---|---|---|
| Public lookup | `verified_indicator WHERE type IN (…) AND normalized_value = X AND status='ACTIVE'` → else `COUNT(DISTINCT report_id)` on `report_indicator` joined to pending reports | Index scan on unique/`idx_ri_type_value` |
| Anonymous rate limit | `COUNT(*) FROM audit WHERE event_type='REPORT_SUBMITTED' AND actor_ip_hash=H AND occurred_at > now()-1h` | `idx_audit_rate` |
| Analyst queue | `status='PENDING' ORDER BY risk_score DESC, created_at` + cluster size subquery | `idx_report_queue` |
| Cluster size | `COUNT(DISTINCT report_id)` per `(type, normalized_value)` over pending reports | `idx_ri_type_value` + partial status |
| Trend charts | `GROUP BY platform, category, date_trunc('day', created_at)` with `SUM(financial_loss)` | `idx_report_platform_cat_created` |
| Spike detection | Compare last 24 h count vs 7-day daily average per group | Same indexes |
| Remedial guides | `tactics @> ARRAY['URGENCY'] AND status='PUBLISHED'` | GIN |
| Re-dispatch scans | `scan_status='PENDING' AND scan_dispatched_at < now()-5min` | partial index |

Scale note: pending cluster size is computed at query time (fine up to ~100k pending rows). If it becomes slow, introduce a `pending_indicator_stats` table maintained in the same transactions as report/verify writes.

## 7. Critical transactions and concurrency

| Operation | Rule |
|---|---|
| Create report | One `atomic` block: report + indicators + evidence rows. S3 upload happens **before** the DB write; on DB failure the uploaded keys are deleted (and an orphan-cleanup job covers crashes). |
| Verify indicator | One `atomic` block: `get_or_create` blacklist row (unique constraint resolves races) → lock pending reports (`select_for_update`, IDs selected first because `DISTINCT` and `FOR UPDATE` can't be combined) → bulk update `PENDING→VERIFIED` → `total_report_count = F('total_report_count') + n` → recompute `threat_level` → link `report_indicator.verified_indicator_id` → write `triage_decision` rows. Audit and metrics after commit. |
| Scan callback | Idempotent: updates only if `scan_status != DONE` or incoming `ruleset_version` is newer; `scan_result` upsert on `report_id`. |
| Rules/config change | Change + `ruleset_version = ruleset_version + 1` in one transaction. |
| Simulator completion | Compute score from stored answers (never from client-sent correctness). |

## 8. Data classification, privacy and retention

| Data | Class | Handling | Proposed retention |
|---|---|---|---|
| `user.email`, `full_name`, `organization` | PII | Not logged; role-gated | Until account deletion |
| `scamreport.message_text`, evidence files | **Sensitive PII** | Analyst-only; evidence private + pre-signed | Rejected: 90 days after review · Verified: 24 months · then delete (rows + S3) |
| `reportindicator.raw_value` | Sensitive | Analyst-only; public sees `display_value`; kept so re-hash migration is possible if `INDICATOR_HMAC_KEY` changes | Same as report |
| `alertsubscription.endpoint` | PII | Hashed copy for lookups; never logged | 30 days after unsubscribe |
| `actor_ip_hash` | Pseudonymous | Salted HMAC via `HMAC_IP_SALT` (IP hashing only; salt rotated per policy; bank accounts use separate non-casually rotated `INDICATOR_HMAC_KEY`) | 90 days (INFO), 365 days (security events) |
| Anonymous reports | No identity link | No reporter, no raw IP | As report |
| `simulator_attempt` | Low | Anonymous plays keyed by random token | Anonymous: 90 days |
| `token_blacklist_*` | Technical | Flush expired daily | Until token expiry |

Retention is enforced by the scheduled `run_jobs` purge tasks (advisory-locked). Confirm the final periods with the lecturer/team and state them in the report.

## 9. DB architecture (physical)

```mermaid
flowchart LR
    subgraph AZa["Availability Zone A"]
        APP1[EC2 app instance 1]
        DBP[(RDS PostgreSQL primary)]
    end
    subgraph AZb["Availability Zone B"]
        APP2[EC2 app instance 2]
        DBS[(RDS standby)]
    end
    APP1 --> DBP
    APP2 --> DBP
    DBP == synchronous replication ==> DBS
    DBP -.-> BK[(Automated backups + PITR)]
    DBP -.-> CW[CloudWatch metrics + Performance Insights]
    DBP -.-> LOG[CloudWatch Logs: postgresql log]
```

| Setting | Value (proposal) |
|---|---|
| Engine / class | PostgreSQL 16; `db.t3.micro` dev, `db.t3.small` demo — confirm after load test |
| Topology | **Multi-AZ** (prod); single-AZ for dev |
| Storage | gp3, 20 GB, storage autoscaling to 50 GB, encrypted (KMS) |
| Network | Private DB subnet group (2 AZs); `db-sg` allows 5432 from `app-sg` only; not publicly accessible |
| Backups | Automated, 7-day retention, point-in-time recovery; one tested restore documented |
| Protection | Deletion protection ON; final snapshot on delete |
| TLS | `rds.force_ssl=1`; Django `OPTIONS: {"sslmode": "require"}` (use `verify-full` + RDS CA bundle if time allows) |
| Parameter group | `timezone=UTC`, `log_min_duration_statement=500`, `idle_in_transaction_session_timeout=60000`; per-connection `statement_timeout=10000` via Django `OPTIONS` |
| Monitoring | Performance Insights, Enhanced Monitoring (60 s), alarms: CPU, connections, free storage, free memory, read/write latency |
| Maintenance | Auto minor upgrades; off-peak window |
| Credentials | SSM SecureString; app user has DML + migrate privileges only (no superuser); separate read-only user for analysts/BI if needed later |

**Connection budget:** `max_instances(4) × workers(3) × threads(4) = 48` + 10 for jobs/migrations = 58. Check the instance's real `max_connections` (derived from memory) and keep usage below 80%. Use `CONN_MAX_AGE=60`. Add RDS Proxy only if the budget is exceeded.

**Scaling path (document, don't build):** read replica for analytics → materialised view `mv_daily_report_stats` refreshed by job → monthly partitioning of `ops_systemauditlog` → `pending_indicator_stats` table → RDS Proxy.

**Migrations:** Django migrations only; expand/contract; run once per release via SSM Run Command (see architecture doc §14); `CREATE INDEX` on large tables uses `AddIndexConcurrently` (`atomic = False` migration).

## 10. Seed and reference data (data migrations / fixtures)

| Data | Source |
|---|---|
| Admin account | `manage.py create_admin` (password from env/SSM), never via API |
| `scanner_scannerconfig` row (`id=1`, ruleset_version 1) | Data migration |
| Default rules | Phase 5 management command (not a migration; requires admin user) |
| Recovery playbooks | Fixture per category × payment method × country (MY, NP, default). Hotline numbers must be verified from official sources |
| Admin-area allow-list | Fixture (Malaysian states, Nepal provinces, other) |
| Demo data | `manage.py seed_demo` for screenshots/load tests only (never in prod) |

## 11. Django modelling checklist (for every model)

- [ ] UUID PK if exposed; `TimeStampedModel` if mutable
- [ ] `TextChoices` + `CheckConstraint` for each enum field
- [ ] Every FK has explicit `on_delete` matching Section 1
- [ ] Explicit index names; indexes from Section 5 added in the same migration as the model
- [ ] `Meta.constraints` for uniqueness and checks
- [ ] No business logic in `save()`; logic lives in services
- [ ] `__str__` never returns PII
- [ ] Factory in `tests/factories.py`; constraint tests exist

## 12. About Prisma

Prisma is a Node.js tool. Django cannot use it, and running Prisma migrations against a Django-managed database would corrupt migration state. The "schema file" equivalent here is: Django models + migrations (executable truth) and this document with the ERD (human truth). If a visual editor is wanted, paste the Mermaid ERD into any Mermaid renderer or convert it to DBML for dbdiagram.io — as documentation only.

## 13. Accepted deviations from this document

The following deviations from the original draft were proposed during implementation and explicitly approved by the project owner:

| Decision | Area | Deviation & Rationale | Evidence |
|---|---|---|---|
| **D4** | Enums | Unified `AudienceGroup` enum (`GENERAL`, `ELDERLY`, `TEENAGER`, `NON_TECH`) across alerts, advisories, and guides; advisories additionally permit `ALL`. Display label for `ELDERLY`: "Seniors & family". | `apps/core/enums.py:AudienceGroup`, `apps/alerts/models.py:ck_sub_audience` |
| **D7** | Auth | User `email` has `unique=True` on model field and functional unique index `uq_user_email_lower` on `Lower('email')`; `UserManager` lowercases email; User model extends `AbstractBaseUser` only (no `PermissionsMixin`). | `apps/accounts/models.py:uq_user_email_lower`, migration `accounts/0001_initial.py` |
| **D10** | Indexes | Truncated `idx_report_platform_cat_created` (31 chars) to `idx_report_plat_cat_created` (27 chars) to satisfy Django's 30-character index name limit. | `apps/reports/models.py:idx_report_plat_cat_created`, migration `reports/0001_initial.py` |
| **D12** | Broadcasts | `ThreatAdvisory.published_by` FK uses `on_delete=models.PROTECT`, matching staff FK conventions in Section 1. | `apps/broadcasts/models.py:published_by`, migration `broadcasts/0001_initial.py` |
| **D13** | Alerts | Added CheckConstraint `ck_sub_categories_elements` using PostgreSQL array containment `<@` for `AlertSubscription.categories`. | `apps/alerts/models.py:ck_sub_categories_elements`, migration `alerts/0001_initial.py` |
| **D14** | Guides | Added PostgreSQL array containment `<@` checks for `audience_groups` and `tactics`. Explicit CHECK constraints for `language`, `readability_mode`, `status`, `asset_type`. `GuideAsset` of type `IMAGE` requires non-empty trimmed `alt_text`. | `apps/literacy/models.py:ck_guide_audience_groups`, `ck_guide_tactics`, `ck_asset_image_alt_text` |
| **D15** | Guides | Added `ck_guide_published_audience` (CARDINALITY >= 1 when status=PUBLISHED), `ck_guide_published_timestamp` (published_at NOT NULL when status=PUBLISHED), and `ck_asset_duration_positive` (duration_seconds NULL or > 0). | `apps/literacy/models.py:ck_guide_published_audience`, `ck_guide_published_timestamp`, `ck_asset_duration_positive` |
| **D16** | Simulator | Added `ck_scenario_scam_has_tactic` (scam scenario tactic <> 'NONE'); `ScenarioRedFlag` `w_pct > 0` and `h_pct > 0`; `SimulatorAttempt` COMPLETED requires completed_at and score_pct NOT NULL; enum CHECKs for channel, tactic, status, flag_code. | `apps/literacy/models.py:ck_scenario_scam_has_tactic`, `ck_flag_w_pct_range`, `ck_flag_h_pct_range`, `ck_attempt_completed_fields` |
| **D17** | Simulator | Added `ck_attempt_scenario_count` (CARDINALITY(scenario_ids) = 5); `ck_answer_flag_only_if_scam` (answered_is_scam = TRUE OR selected_flag_code IS NULL); `ScenarioTactic` = `Tactic.values` + "NONE"; `started_at` has Django-side default `timezone.now`. | `apps/literacy/models.py:ck_attempt_scenario_count`, `ck_answer_flag_only_if_scam` |
| **D18** | Scanner & Ops | Added `ck_rule_pattern_lowercase` (pattern = LOWER(pattern)); `ck_rule_pattern_not_blank`; `ScannerConfig` boundary constraints (points 0..100, threshold 1..100, ruleset_version >= 1, id=1); `ScanResult.breakdown` jsonb_typeof = 'array'; `SystemAuditLog.metadata` jsonb_typeof = 'object', default=dict; `target_type` and `target_id` co-presence constraint; enum checks for rule_type, audit event_type, severity. | `apps/scanner/models.py:ck_rule_pattern_lowercase`, `ck_config_singleton`, `ck_scan_breakdown_is_array`, `apps/ops/models.py:ck_audit_metadata_is_object`, `ck_audit_target_pair` |
| **D19** | Scanner | `ScannerConfig` singleton (`id=1`, `ruleset_version=1`) seeded via data migration `scanner 0002_seed_scanner_config`. Default rules deferred to Phase 5 management command. | migration `scanner/0002_seed_scanner_config.py` |
| **D20** | Safety-net | Permanent schema inventory test `backend/apps/core/tests/test_schema_inventory.py` asserting exact 25 public tables, no duplicate index column sets, and exact named constraints and indexes. | `apps/core/tests/test_schema_inventory.py` |
| **D21** | ERD | `docs/erd.md` generated from Django models via `backend/tools/generate_erd.py`. | `backend/tools/generate_erd.py`, `docs/erd.md` |
| **D22** | Types | Fixed-length `char(n)` columns in 03a are implemented as `varchar(n)` because Django has no fixed-length type. Affected: `currency(3)`, `country_code(2)` on scamreport and recoveryplaybook, `sha256(64)`, `endpoint_hash(64)`, `unsubscribe_token_hash(64)`, `actor_ip_hash(64)`, `language(2)`. Exact lengths enforced by services and validators (Phases 4 and 7); `language` already has an enum CHECK. | `apps/reports/models.py`, `apps/alerts/models.py`, `apps/ops/models.py`, `apps/literacy/models.py` |
| **D23** | Defaults | `public_note` (`intel_verifiedindicator`) and `alt_text` (`literacy_guideasset`) are `NOT NULL` with empty-string default; the database has no column defaults, because Django applies defaults in Python. | `apps/intel/models.py:public_note`, `apps/literacy/models.py:alt_text`, migrations `intel/0001_initial.py`, `literacy/0001_initial.py` |

