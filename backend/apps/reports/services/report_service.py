import dataclasses
import datetime
import hashlib
import hmac
import logging
import secrets
import uuid

from django.db import IntegrityError, transaction
from rest_framework import exceptions

from apps.core import audit, metrics
from apps.ops.models import AuditEventType, AuditSeverity
from apps.reports import evidence
from apps.reports.constants import (
    CROCKFORD_ALPHABET,
    MAX_EVIDENCE_FILES,
    MAX_SUBMITTED_INDICATORS,
    MAX_TOTAL_INDICATORS,
    MIN_SUBMITTED_INDICATORS,
)
from apps.reports.models import (
    IndicatorType,
    PaymentMethod,
    ReportEvidence,
    ReportIndicator,
    ReportStatus,
    ScamReport,
    ScanStatus,
)
from apps.reports.normalizers import (
    normalize_bank_account,
    normalize_domain,
    normalize_email,
    normalize_phone,
    normalize_url,
)
from apps.reports.selectors.report_selectors import get_recovery_playbook
from apps.reports.throttling import (
    check_report_submission_throttle,
    check_report_tracking_throttle,
)
from apps.reports.validators import (
    validate_admin_area,
    validate_country_code,
    validate_currency,
    validate_financial_loss,
    validate_message_text,
)
from apps.scanner.services import scanner_service

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ReportSubmissionResult:
    report: ScamReport
    access_key: str | None
    playbook: dict
    is_replay: bool = False


def generate_reference_code() -> str:
    """
    Generates a unique reference code per D61:
    Format: SCM-<YYYY>-<8 Crockford characters>
    Retries up to 5 times on database collision.
    """
    year = datetime.date.today().year
    for _ in range(5):
        random_chars = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(8))
        ref_code = f"SCM-{year}-{random_chars}"
        if not ScamReport.objects.filter(reference_code=ref_code).exists():
            return ref_code
    raise RuntimeError("Failed to generate a unique reference code after 5 attempts.")


def create_report(
    *,
    category: str,
    platform: str,
    message_text: str,
    country_code: str,
    currency: str,
    financial_loss=0,
    payment_method: str = PaymentMethod.NONE,
    admin_area: str | None = None,
    incident_date: datetime.date | None = None,
    indicators: list[dict] | None = None,
    evidence_files: list[bytes] | None = None,
    client_submission_id: uuid.UUID | None = None,
    anonymous: bool = False,
    user=None,
    ip_hash: str = "",
    request_id: str | None = None,
) -> ReportSubmissionResult:
    """
    Core report submission service satisfying D54-D75:
    1. Idempotency lookup via client_submission_id (D62)
    2. Rate limit check (D47, D63)
    3. Input validation and indicator normalisation (D55, D56, D57)
    4. Evidence processing and S3 upload (D58, D72, D73)
    5. Atomic DB write with audit log (D59, D70)
    6. Post-commit metric and scan dispatch (D70)
    """
    # 1. Idempotency lookup
    if client_submission_id:
        existing = ScamReport.objects.filter(
            client_submission_id=client_submission_id
        ).first()
        if existing:
            playbook = get_recovery_playbook(
                category=existing.category,
                payment_method=existing.payment_method,
                country_code=existing.country_code,
                financial_loss=existing.financial_loss,
            )
            return ReportSubmissionResult(
                report=existing,
                access_key=None,
                playbook=playbook,
                is_replay=True,
            )

    # Determine anonymous vs authenticated (D69)
    is_anon = anonymous or user is None or not getattr(user, "is_authenticated", False)
    auth_user = None if is_anon else user

    # 2. Rate limit check (replays do not count per D70)
    check_report_submission_throttle(ip_hash=ip_hash, user=auth_user)

    # 3. Input validation
    validate_country_code(country_code)
    validate_currency(currency)
    validate_admin_area(country_code, admin_area)
    clean_message = validate_message_text(message_text)
    clean_loss = validate_financial_loss(financial_loss, payment_method)

    # Indicator validation and normalisation (D1, D56, D57)
    raw_indicators = indicators or []
    if len(raw_indicators) < MIN_SUBMITTED_INDICATORS:
        raise exceptions.ValidationError(
            {"indicators": [f"At least {MIN_SUBMITTED_INDICATORS} indicator is required."]}
        )
    if len(raw_indicators) > MAX_SUBMITTED_INDICATORS:
        raise exceptions.ValidationError(
            {"indicators": [f"At most {MAX_SUBMITTED_INDICATORS} indicators may be submitted."]}
        )

    processed_indicators = []
    seen_indicator_keys = set()

    for idx, ind in enumerate(raw_indicators):
        ind_type = ind.get("type")
        raw_val = str(ind.get("value") or "").strip()
        if not ind_type or not raw_val:
            raise exceptions.ValidationError(
                {"indicators": [{idx: "Indicator must include 'type' and 'value'."}]}
            )

        if ind_type == IndicatorType.PHONE:
            norm_val, disp_val = normalize_phone(raw_val, country_code)
            key = (IndicatorType.PHONE, norm_val)
            if key not in seen_indicator_keys:
                seen_indicator_keys.add(key)
                processed_indicators.append({
                    "type": IndicatorType.PHONE,
                    "raw_value": raw_val,
                    "normalized_value": norm_val,
                    "display_value": disp_val,
                })

        elif ind_type == IndicatorType.URL:
            norm_val, disp_val, derived_dom = normalize_url(raw_val)
            key = (IndicatorType.URL, norm_val)
            if key not in seen_indicator_keys:
                seen_indicator_keys.add(key)
                processed_indicators.append({
                    "type": IndicatorType.URL,
                    "raw_value": raw_val,
                    "normalized_value": norm_val,
                    "display_value": disp_val,
                })

            # Auto-derive DOMAIN row per D56 (does not count toward submitted indicator count)
            if derived_dom:
                dom_key = (IndicatorType.DOMAIN, derived_dom)
                if dom_key not in seen_indicator_keys:
                    seen_indicator_keys.add(dom_key)
                    processed_indicators.append({
                        "type": IndicatorType.DOMAIN,
                        "raw_value": derived_dom,
                        "normalized_value": derived_dom,
                        "display_value": derived_dom,
                    })

        elif ind_type == IndicatorType.DOMAIN:
            norm_val, disp_val = normalize_domain(raw_val)
            key = (IndicatorType.DOMAIN, norm_val)
            if key not in seen_indicator_keys:
                seen_indicator_keys.add(key)
                processed_indicators.append({
                    "type": IndicatorType.DOMAIN,
                    "raw_value": raw_val,
                    "normalized_value": norm_val,
                    "display_value": disp_val,
                })

        elif ind_type == IndicatorType.EMAIL:
            norm_val, disp_val = normalize_email(raw_val)
            key = (IndicatorType.EMAIL, norm_val)
            if key not in seen_indicator_keys:
                seen_indicator_keys.add(key)
                processed_indicators.append({
                    "type": IndicatorType.EMAIL,
                    "raw_value": raw_val,
                    "normalized_value": norm_val,
                    "display_value": disp_val,
                })

        elif ind_type == IndicatorType.BANK_ACCOUNT:
            norm_val, disp_val = normalize_bank_account(raw_val)
            key = (IndicatorType.BANK_ACCOUNT, norm_val)
            if key not in seen_indicator_keys:
                seen_indicator_keys.add(key)
                processed_indicators.append({
                    "type": IndicatorType.BANK_ACCOUNT,
                    "raw_value": raw_val,
                    "normalized_value": norm_val,
                    "display_value": disp_val,
                })
        else:
            raise exceptions.ValidationError(
                {"indicators": [{idx: f"Unsupported indicator type '{ind_type}'."}]}
            )

    if len(processed_indicators) > MAX_TOTAL_INDICATORS:
        raise exceptions.ValidationError(
            {"indicators": [f"Total indicators cannot exceed {MAX_TOTAL_INDICATORS}."]}
        )

    # 4. Evidence processing (D58)
    files_to_process = evidence_files or []
    if len(files_to_process) > MAX_EVIDENCE_FILES:
        raise exceptions.ValidationError(
            {"evidence": [f"At most {MAX_EVIDENCE_FILES} evidence files are permitted."]}
        )

    processed_evidence = []
    for file_bytes in files_to_process:
        clean_bytes, content_type, ext, sha256_hex = (
            evidence.validate_and_process_evidence_file(file_bytes)
        )
        processed_evidence.append({
            "bytes": clean_bytes,
            "content_type": content_type,
            "ext": ext,
            "sha256": sha256_hex,
        })

    # Pre-generate IDs and tokens
    report_id = uuid.uuid4()
    ref_code = generate_reference_code()

    if is_anon:
        access_key = secrets.token_hex(16)  # 128-bit random token
        access_key_hash = hashlib.sha256(access_key.encode("utf-8")).hexdigest()
        reporter = None
        audit_actor = None
    else:
        access_key = None
        access_key_hash = None
        reporter = auth_user
        audit_actor = auth_user

    # 4b. S3 upload before DB transaction per D59
    uploaded_records = []
    uploaded_keys = []
    for ev in processed_evidence:
        s3_key, sha256_hex, size_bytes = evidence.upload_evidence(
            report_id=report_id,
            file_bytes=ev["bytes"],
            content_type=ev["content_type"],
            ext=ev["ext"],
        )
        uploaded_keys.append(s3_key)
        uploaded_records.append({
            "s3_key": s3_key,
            "content_type": ev["content_type"],
            "size_bytes": size_bytes,
            "sha256": sha256_hex,
        })

    # 5. Atomic DB write
    try:
        with transaction.atomic():
            report = ScamReport.objects.create(
                id=report_id,
                reference_code=ref_code,
                client_submission_id=client_submission_id,
                reporter=reporter,
                is_anonymous=is_anon,
                access_key_hash=access_key_hash,
                category=category,
                platform=platform,
                message_text=clean_message,
                financial_loss=clean_loss,
                currency=currency,
                payment_method=payment_method,
                country_code=country_code,
                admin_area=admin_area,
                incident_date=incident_date,
                status=ReportStatus.PENDING,
                scan_status=ScanStatus.PENDING,
            )

            # Insert indicators
            ReportIndicator.objects.bulk_create([
                ReportIndicator(
                    report=report,
                    type=ind["type"],
                    raw_value=ind["raw_value"],
                    normalized_value=ind["normalized_value"],
                    display_value=ind["display_value"],
                )
                for ind in processed_indicators
            ])

            # Insert evidence records
            ReportEvidence.objects.bulk_create([
                ReportEvidence(
                    report=report,
                    s3_key=rec["s3_key"],
                    content_type=rec["content_type"],
                    size_bytes=rec["size_bytes"],
                    sha256=rec["sha256"],
                )
                for rec in uploaded_records
            ])

            # Write audit log (D70: inside atomic transaction)
            audit.log_event(
                event_type=AuditEventType.REPORT_SUBMITTED,
                actor=audit_actor,
                ip_hash=ip_hash,
                target=report,
                metadata={
                    "category": report.category,
                    "platform": report.platform,
                    "indicator_count": len(processed_indicators),
                    "file_count": len(uploaded_records),
                },
                severity=AuditSeverity.INFO,
                request_id=request_id,
            )

    except IntegrityError as exc:
        # Concurrent race on client_submission_id per D70
        evidence.delete_evidence_keys(uploaded_keys)
        if client_submission_id:
            existing = ScamReport.objects.filter(
                client_submission_id=client_submission_id
            ).first()
            if existing:
                playbook = get_recovery_playbook(
                    category=existing.category,
                    payment_method=existing.payment_method,
                    country_code=existing.country_code,
                    financial_loss=existing.financial_loss,
                )
                return ReportSubmissionResult(
                    report=existing,
                    access_key=None,
                    playbook=playbook,
                    is_replay=True,
                )
        raise exc
    except Exception as exc:
        # Delete S3 keys on any DB failure per D59
        evidence.delete_evidence_keys(uploaded_keys)
        raise exc

    # 6. Post-commit hooks (D70)
    transaction.on_commit(
        lambda: metrics.emit(
            "ReportsSubmitted",
            1,
            dims={"Platform": report.platform},
        )
    )
    transaction.on_commit(lambda: scanner_service.dispatch_scan(report.id))

    playbook = get_recovery_playbook(
        category=report.category,
        payment_method=report.payment_method,
        country_code=report.country_code,
        financial_loss=report.financial_loss,
    )

    return ReportSubmissionResult(
        report=report,
        access_key=access_key,
        playbook=playbook,
        is_replay=False,
    )


def track_report(
    *,
    reference_code: str,
    access_key: str | None = None,
    user=None,
    ip_hash: str = "",
) -> tuple[ScamReport, dict]:
    """
    Public report tracking service per D54, D61, D63:
    - Rate limits failed attempts via audit log (max 10 / 15 min).
    - Constant-time access_key_hash comparison.
    - Uniform 404 response on unknown reference or bad access key (prevents enumeration).
    Returns (report, playbook).
    """
    check_report_tracking_throttle(ip_hash=ip_hash)

    report = ScamReport.objects.filter(reference_code=reference_code).first()

    # Uniform 404 helper
    def _fail_not_found():
        audit.log_event(
            event_type=AuditEventType.REPORT_TRACK_FAILED,
            ip_hash=ip_hash,
            metadata={"ref_code": reference_code},
            severity=AuditSeverity.WARN,
        )
        raise exceptions.NotFound("Report not found.")

    if not report:
        _fail_not_found()

    # Anonymous report authentication via access_key
    if report.is_anonymous:
        if not access_key or not report.access_key_hash:
            _fail_not_found()
        given_hash = hashlib.sha256(access_key.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(report.access_key_hash, given_hash):
            _fail_not_found()
    else:
        # Registered user report: accessible if authenticated user matches reporter
        if user and getattr(user, "is_authenticated", False) and report.reporter_id == user.id:
            pass
        else:
            _fail_not_found()

    playbook = get_recovery_playbook(
        category=report.category,
        payment_method=report.payment_method,
        country_code=report.country_code,
        financial_loss=report.financial_loss,
    )

    return report, playbook
