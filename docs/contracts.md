# Cross-Student Contracts (Phase 1A)

**Status:** FROZEN  
**Origin:** `docs/03-backend-build-plan.md` §Phase 1A  
**Related:** `01-project-overview.md` · `02-project-architecture.md` · `03a-database-design.md` · `PROGRESS.md`

These contracts define the boundaries between student modules (S1, S2, S3, S4). Changing any signature or contract requires unanimous approval from all four students and an update to `PROGRESS.md`.

---

## 1. Summary Contract Table

| Contract | Owner | Consumers | Description |
|---|---|---|---|
| `core.audit.log_event(event_type, *, actor=None, ip_hash=None, target=None, metadata=None, severity="INFO")` | S4 | all | Append-only audit logger. Writes `ops_systemauditlog`. Never logs PII. Non-blocking. |
| `core.metrics.emit(name, value=1, unit="Count", dims=None)` | S4 | S1, S2 | CloudWatch custom metric emitter. Non-raising; fails safe on AWS network issues. |
| `core.ip.client_ip_hash(request)` | S4 | S1, S4 | Extracts client IP at `TRUSTED_PROXY_HOPS` depth and returns HMAC-SHA256 hex using `HMAC_IP_SALT`. |
| `core.aws.client(service)` | S4 | all | Central `boto3` client factory with explicit timeouts (`connect=2s`, `read=5s`) and retry limit (2). |
| `scanner_service.dispatch_scan(report_id)` | S4 | S1 | Gathers report text, indicators, rules, config, and prior counts; triggers Lambda asynchronously on DB commit. |
| `intel.selectors.find_active_indicators(pairs)` and `count_pending_by_indicator(pairs)` | S2 | S1 (lookup) | Evaluates indicator `(type, normalized_value)` pairs against active blacklist and pending report counts. |
| `alerts` model `AlertSubscription` + `sns_service.publish_advisory()` | S1 owns subscriptions, S2 owns publish | S2 reads subscribers only through SNS | S2 broadcasts threat advisories via SNS message attributes (`audience`, `category`); direct SQL cross-read is prohibited. |
| `literacy.selectors.guides_for_tactics(tactics)` | S3 | S3 (simulator) | Returns published educational guides tagged with specified manipulation tactics for remediation. |
| Error codes + envelope | S4 (`core.errors`) | all | Standardized DRF exception envelope `{"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}`. |
| SNS topics (`scamshield-alerts-{env}`, `scamshield-staff-{env}`) | S4 creates (infra) | S1 subscribe, S2 publish | Infrastructure topics. S1 manages subscriber endpoints; S2 publishes public advisories; scanner notifies staff topic. |

---

## 2. Shared Types and Enums (Governed by D1–D6)

### 2.1 Shared Audience Group Enum (`AudienceGroup` — D4)
Replaces separate `TargetGroup` and `Audience` enums. Shared across `alerts`, `broadcasts`, and `literacy`.

```python
class AudienceGroup(models.TextChoices):
    GENERAL = "GENERAL", "General Public"
    ELDERLY = "ELDERLY", "Seniors & family"  # UI display label per D4
    TEENAGER = "TEENAGER", "Teenagers & Students"
    NON_TECH = "NON_TECH", "Non-Technical Users"
```
*Note:* Advisories (`THREAT_ADVISORY.target_audience`) additionally accept `"ALL"`.

### 2.2 Indicator Submission & Normalisation Contract (D1, D2, D5)
- **Submission Limit (D1):** Citizens submit between 1 and 5 indicators (`≥ 1, ≤ 5`). Auto-derived `DOMAIN` rows (from `URL`s) do not count toward this limit. Maximum 10 total indicator rows per report. Enforced in service/serializer layer, not in DB.
- **Bank Account Normalisation & Hashing (D2, D5):**
  - Normalisation: Strip spaces, dashes, and dots; keep digits only; retain leading zeros; no bank-specific format rules (known limitation).
  - Hashing: `normalized_value` is `HMAC_SHA256(INDICATOR_HMAC_KEY, clean_digits).hexdigest()`.
  - Secret: `INDICATOR_HMAC_KEY` is dedicated and not casually rotated. `raw_value` is retained to permit future re-hash migrations.
- **IP Hashing (D2):**
  - Salt: `HMAC_IP_SALT` is dedicated strictly to client IP hashing and may rotate per policy.

---

## 3. Detailed Component Specifications

### 3.1 `core.audit.log_event` (Owner: S4)
```python
def log_event(
    event_type: str,
    *,
    actor: Optional[User] = None,
    ip_hash: Optional[str] = None,
    target: Optional[Any] = None,
    metadata: Optional[dict] = None,
    severity: str = "INFO",
    request_id: Optional[str] = None,
) -> SystemAuditLog:
    """Records security and operational actions to ops_systemauditlog.
    Guarantees no PII in metadata. Never raises to caller on failure.
    """
```

### 3.2 `core.metrics.emit` (Owner: S4)
```python
def emit(
    name: str,
    value: float = 1,
    unit: str = "Count",
    dims: Optional[dict[str, str]] = None,
) -> None:
    """Emits custom CloudWatch metric under 'ScamShield/Operations'.
    Fails silently with a logged warning if CloudWatch is unreachable.
    """
```

### 3.3 `core.ip.client_ip_hash` (Owner: S4)
```python
def client_ip_hash(request: HttpRequest) -> str:
    """Extracts client IP from X-Forwarded-For at TRUSTED_PROXY_HOPS depth.
    Computes HMAC-SHA256 hex digest using HMAC_IP_SALT.
    """
```

### 3.4 `core.aws.client` (Owner: S4)
```python
def client(service_name: str) -> boto3.client:
    """Returns a boto3 client configured with connect_timeout=2,
    read_timeout=5, and max_attempts=2.
    """
```

### 3.5 `scanner_service.dispatch_scan` (Owner: S4, Consumer: S1)
```python
def dispatch_scan(report_id: UUID) -> None:
    """Collects report narrative, indicators, active rules, and config.
    Computes per-indicator prior pending counts. Invokes Lambda scanner
    asynchronously (InvocationType='Event') via transaction.on_commit().
    """
```

### 3.6 `intel.selectors` (Owner: S2, Consumer: S1)
```python
def find_active_indicators(pairs: list[tuple[str, str]]) -> QuerySet[VerifiedIndicator]:
    """Finds ACTIVE verified blacklist indicators for [(type, normalized_value), ...]."""

def count_pending_by_indicator(pairs: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """Returns count of distinct pending reports linked to each indicator pair."""
```

### 3.7 `alerts` & `broadcasts` Boundary (S1 / S2)
- S1 manages `AlertSubscription` storage, confirmation tokens, and AWS SNS subscriber filter policies.
- S2 publishes advisories using `boto3` SNS publish with `MessageAttributes={"audience": ..., "category": ...}`.
- S2 never queries `AlertSubscription` directly; AWS SNS handles all topic subscriber fan-out.
- SMS alerting remains behind a feature flag, OFF by default (D6).

### 3.8 `literacy.selectors.guides_for_tactics` (Owner: S3, Consumer: S3)
```python
def guides_for_tactics(tactics: list[str], language: str = "en") -> QuerySet[EducationalGuide]:
    """Retrieves published educational guides matching blind-spot tactics."""
```
