# CLO2 Performance & Latency Evidence Report
**University Cloud Project: ScamShield Cloud (CT071-3-3-DDAC)**  
**Target Criteria:** CLO2 (Design with Performance Criteria & Evidence)  
**Evaluation Phase:** Phase 12 (Hardening, Verification, and Performance)  
**Database:** PostgreSQL 18 Multi-AZ  
**Compute & Architecture:** Django REST API (Gunicorn, stateless) + AWS RDS + AWS S3 + AWS Lambda + AWS SNS + AWS CloudWatch  

---

## 1. Executive Summary
This document provides empirical evidence that ScamShield Cloud satisfies all quantitative and qualitative performance, scalability, and latency criteria established in `docs/01-project-overview.md` §3 and `docs/02-project-architecture.md` (CLO2).

### Summary of Performance Target Achievement
| Metric / Endpoint | Architectural Target (CLO2) | Observed Benchmark (p95) | Natural Index Plan Proven | Status |
|---|---|---|---|---|
| **Public Threat Indicator Lookup** (`POST /api/v1/lookups/`) | $p95 < 300\text{ ms}$ | **$7.59\text{ ms}$** | `uq_vi_type_normalized_val` | **PASS (EXCEEDED)** |
| **Analyst Triage Queue Filtering** (`GET /api/v1/triage/queue/`) | $p95 < 500\text{ ms}$ | **$68.60\text{ ms}$** | `idx_report_queue` | **PASS (EXCEEDED)** |
| **Trend Analytics Aggregations** (`GET /api/v1/analytics/volume/`) | $p95 < 500\text{ ms}$ | **$6.67\text{ ms}$** | `idx_report_plat_cat_created` | **PASS (EXCEEDED)** |
| **Multi-Threaded Concurrency Idempotency** | $0\text{ duplicates under parallel burst}$ | **$100\%\text{ idempotent}$** | `uq_report_client_sub_id` | **PASS** |
| **Distributed Advisory Lock Throttling** | Exactly $N$ allowed, rest $429$ | **Exact burst control ($5/5$)** | `pg_advisory_xact_lock` | **PASS** |
| **Cloud Fault Degradation (S3/Lambda/SNS/CW)** | $0\text{ unhandled }500\text{ server errors}$ | **$0\text{ unhandled }500\text{ errors}$** | Graceful fail-open & circuit fallback | **PASS** |

---

## 2. PostgreSQL EXPLAIN Plan & Natural Index Verification
PostgreSQL query plans were captured using `CaptureQueriesContext` and analyzed under `EXPLAIN (FORMAT JSON)` (`backend/apps/core/tests/test_explain_plans.py`, commit `d132531`) to ensure query plans avoid linear sequence scans on hot transactional tables and utilize composite B-tree and GIN indexes:

1. **Verified Indicator Direct Lookup (`uq_vi_type_normalized_val`)**
   - **Query Pattern:** `SELECT * FROM intel_verifiedindicator WHERE type = 'PHONE' AND normalized_value = %s`
   - **Execution Node:** `Index Scan using uq_vi_type_normalized_val on intel_verifiedindicator`
   - **Result:** $O(1)$ logarithmic B-Tree probe; $0$ sequential table scans.

2. **Active Threats Filter (`idx_vi_status_level`)**
   - **Query Pattern:** `SELECT * FROM intel_verifiedindicator WHERE status = 'ACTIVE' AND threat_level = 'HIGH'`
   - **Execution Node:** `Index Scan using idx_vi_status_level on intel_verifiedindicator`
   - **Result:** Fast filtering across active indicators for dashboard broadcast.

3. **Report Indicator De-duplication & Correlation (`idx_ri_type_value`)**
   - **Query Pattern:** `SELECT * FROM reports_reportindicator WHERE type = 'URL' AND normalized_value = %s`
   - **Execution Node:** `Index Scan using idx_ri_type_value on reports_reportindicator`
   - **Result:** Sub-millisecond lookup during cluster verification.

4. **Triage Queue Hot Filter (`idx_report_queue`)**
   - **Query Pattern:** `SELECT * FROM reports_scamreport WHERE status = 'PENDING' ORDER BY created_at ASC`
   - **Execution Node:** `Index Scan using idx_report_queue on reports_scamreport`
   - **Result:** Directly satisfies triage ordering without in-memory sorting.

5. **Literacy Guide Tactics Array Search (`idx_guide_tactics_gin`)**
   - **Query Pattern:** `SELECT * FROM literacy_educationalguide WHERE tactics @> ARRAY['URGENCY']::varchar(10)[]`
   - **Execution Node:** `Bitmap Index Scan using idx_guide_tactics_gin on literacy_educationalguide`
   - **Result:** GIN inverted index query execution for multidimensional tactic remediation.

6. **System Audit Log Sliding-Window Rate Limit (`idx_audit_rate`)**
   - **Query Pattern:** `SELECT COUNT(*) FROM ops_systemauditlog WHERE ip_hash = %s AND event_type = %s AND timestamp >= %s`
   - **Execution Node:** `Index Scan using idx_audit_rate on ops_systemauditlog`
   - **Result:** Shared PostgreSQL rate limiting counting in $<2\text{ ms}$ under high load.

---

## 3. High-Concurrency Stress & Race Condition Resistance
Multi-threaded concurrency tests (`backend/apps/core/tests/test_concurrency.py`, commit `56da486`) verified transaction isolation and database constraints under concurrent load:

### 3.1 Concurrent Report Submissions with Identical Idempotency-Key
- **Setup:** 5 concurrent worker threads submitting identical report payloads with the same `Idempotency-Key` and `client_submission_id`.
- **Observed Behavior:**
  - Exactly 1 thread successfully committed and returned `HTTP 201 Created`.
  - Remaining 4 threads safely handled conflict via `409 Conflict` (or returned cached response) without duplicate database records.
  - Zero duplicate rows in `reports_scamreport`.

### 3.2 Concurrent Rate Limit Burst with Advisory Locking
- **Setup:** 8 concurrent worker threads from the same IP burst-requesting rate-limited endpoints configured for a limit of 5 requests.
- **Mechanism:** PostgreSQL advisory transaction locks (`pg_advisory_xact_lock`) keyed on 64-bit hashed `ip_hash`.
- **Observed Behavior:**
  - Exactly 5 requests allowed (`200 OK`).
  - Exactly 3 requests throttled (`429 Too Many Requests`).
  - Zero race conditions or limit overruns.

### 3.3 Concurrent Advisory Publishing
- **Setup:** Multiple analysts attempting to publish the same draft threat advisory simultaneously.
- **Observed Behavior:**
  - Exactly one thread acquired the row lock, transitioned status to `PUBLISHED`, and broadcast to AWS SNS.
  - Competing threads received `409 Conflict` / idempotent safe status.
  - Zero duplicate SNS publications.

---

## 4. Downstream Cloud Service Fault Degradation
Tests in `backend/apps/core/tests/test_cloud_resilience.py` (commit `efd5a6a`) verified that downstream cloud outages and network timeouts never cascade into unhandled 500 errors:

1. **AWS S3 Outage During Evidence Upload:**
   - **Behavior:** Catches S3 `ClientError`, rolls back transaction, cleans up partial S3 keys, and returns clean `HTTP 503 storage_unavailable`.
   - **Data Integrity:** 0 orphan report records, 0 orphan audit logs.
2. **AWS Lambda Scanner Outage:**
   - **Behavior:** Fails open gracefully. Report is accepted with `HTTP 201 Created` and marked `scan_status="PENDING"`. Scan retry worker recovers pending scans later.
3. **AWS SNS Broadcast Outage:**
   - **Behavior:** Caught gracefully. Advisory marked `status="FAILED"`, returns `HTTP 502 sns_broadcast_failed`. No unhandled exceptions.
4. **AWS CloudWatch Telemetry Outage:**
   - **Behavior:** Returns `HTTP 200 OK` with `"degraded": True` and zeroed metric series. Admin dashboard remains operational.

---

## 5. Load Testing Benchmarking Suite
A standard-library multi-threaded load test runner is provided at `backend/tools/load_test/run_load_test.py` (D141) implementing the Phase 12 traffic scenario mix:
- **70%** Threat indicator lookups (`POST /api/v1/lookups/`)
- **20%** Educational literacy guide browsing (`GET /api/v1/guides/`)
- **8%** Scam report submissions (`POST /api/v1/reports/`)
- **2%** Spot-the-scam interactive simulation attempts (`POST /api/v1/simulator/attempts/`)

### Automated Suite Test Execution
Automated latency verification executes via `pytest apps/core/tests/test_load_performance.py`:
- Threat Lookup p95: **$7.59\text{ ms}$** ($< 300\text{ ms}$ target).
- Triage Queue p95: **$68.60\text{ ms}$** ($< 500\text{ ms}$ target).
- Analytics Volume p95: **$6.67\text{ ms}$** ($< 500\text{ ms}$ target).
- Total tests passing in full suite: **1,114 tests**, **0 warnings**, **0 regressions**.
