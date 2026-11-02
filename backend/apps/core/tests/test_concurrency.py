"""
Multi-Threaded Concurrency, Race Condition & Idempotency Test Suite (Task 12.4, Decisions D110, D139).

Verifies race resilience and exact atomicity under concurrent execution:
1. Concurrent report submissions with identical Idempotency-Key (single row created, replay returned, zero deadlocks).
2. Concurrent rate limit checks under burst requests from same IP hash (exact threshold enforcement via advisory lock).
3. Concurrent threat advisory publishing (TO BE PROVEN #16: single publish guarantee, row-level select_for_update, 409 Conflict).
"""

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.db import connection, transaction
from rest_framework import exceptions

from apps.accounts.models import ApprovalStatus, Role, User
from apps.broadcasts.models import AdvisorySeverity, AdvisoryStatus, ThreatAdvisory
from apps.broadcasts.services.broadcast_service import publish_advisory
from apps.core.exceptions import ConflictError
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.reports.models import IndicatorType, PaymentMethod, Platform, ScamCategory, ScamReport
from apps.reports.services.report_service import create_report
from apps.reports.throttling import _ip_hash_to_lock_id, check_report_submission_throttle


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst_concurrency@scamshield.gov",
        password="TestPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
class TestConcurrencyAndIdempotency:
    """Multi-threaded tests for critical concurrent paths."""

    def test_concurrent_report_submissions_identical_idempotency_key(self):
        """
        TO BE PROVEN #8 & D70: Simultaneous report submissions with identical Idempotency-Key.
        Exactly one worker creates the report; the concurrent racer handles the collision
        gracefully and returns a clean replay response with the identical reference code.
        Zero duplicate database rows; zero 500 errors.
        """
        shared_key = uuid.uuid4()
        num_workers = 4
        results = []

        def submit_worker(worker_id):
            connection.close()
            try:
                res = create_report(
                    category=ScamCategory.PHISHING.value,
                    platform=Platform.WHATSAPP.value,
                    message_text=f"Concurrent submission worker {worker_id}",
                    country_code="MY",
                    currency="MYR",
                    financial_loss=Decimal("0.00"),
                    payment_method=PaymentMethod.NONE.value,
                    indicators=[{"type": IndicatorType.PHONE.value, "value": f"+6012000{worker_id:04d}"}],
                    client_submission_id=shared_key,
                    anonymous=True,
                    ip_hash=f"{worker_id:064x}",
                )
                return ("SUCCESS", res.report.reference_code, res.is_replay)
            except Exception as e:
                return ("ERROR", str(e), False)
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(submit_worker, i) for i in range(num_workers)]
            for fut in as_completed(futures, timeout=15):
                results.append(fut.result())

        # Zero unexpected errors
        errors = [r for r in results if r[0] == "ERROR"]
        assert len(errors) == 0, f"Concurrent submissions raised unexpected errors: {errors}"

        # All workers must return the exact same reference code
        ref_codes = {r[1] for r in results}
        assert len(ref_codes) == 1, f"Expected 1 unique reference code, got: {ref_codes}"

        # Exactly 1 primary creation and (num_workers - 1) replays
        replays = [r[2] for r in results]
        assert replays.count(False) == 1, "Expected exactly 1 primary submission"
        assert replays.count(True) == num_workers - 1, f"Expected {num_workers - 1} replays"

        # Exactly one ScamReport row exists in the database
        assert ScamReport.objects.filter(client_submission_id=shared_key).count() == 1

    def test_concurrent_rate_limiting_advisory_lock_burst(self):
        """
        D139: Simultaneous report submission rate limit checks from the same IP hash.
        With 10 concurrent threads checking rate limits where limit=5, exactly 5 threads
        must pass without error, and subsequent threads must receive Throttled exceptions
        with RATE_LIMIT_BLOCK audit rows. Zero race condition over-allowance.
        """
        shared_ip_hash = "deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678"
        num_threads = 10
        results = []

        def throttle_worker(worker_id):
            connection.close()
            try:
                # Atomically check and write audit log on pass under per-ip advisory lock
                with transaction.atomic():
                    if connection.vendor == "postgresql":
                        lock_id = _ip_hash_to_lock_id(shared_ip_hash)
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
                    check_report_submission_throttle(ip_hash=shared_ip_hash, user=None)
                    # If passed, record an audit event inside transaction to simulate report creation
                    SystemAuditLog.objects.create(
                        event_type=AuditEventType.REPORT_SUBMITTED.value,
                        severity="INFO",
                        actor_ip_hash=shared_ip_hash,
                    )
                return ("ALLOWED", worker_id)
            except exceptions.Throttled:
                return ("THROTTLED", worker_id)
            except Exception as e:
                return ("ERROR", str(e))
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(throttle_worker, i) for i in range(num_threads)]
            for fut in as_completed(futures, timeout=15):
                results.append(fut.result())

        errors = [r for r in results if r[0] == "ERROR"]
        assert len(errors) == 0, f"Encountered unexpected errors during throttle burst: {errors}"

        statuses = [r[0] for r in results]
        allowed_count = statuses.count("ALLOWED")
        throttled_count = statuses.count("THROTTLED")

        # Threshold is exactly 5 per IP per hour
        assert allowed_count == 5, f"Expected exactly 5 allowed requests, got {allowed_count}"
        assert throttled_count == num_threads - 5, f"Expected {num_threads - 5} throttled, got {throttled_count}"

    def test_concurrent_advisory_publishing_double_click_idempotency(self, analyst_user):
        """
        TO BE PROVEN #16 (D110): Simultaneous publish requests on the same ThreatAdvisory.
        select_for_update() row lock guarantees that exactly ONE worker publishes the advisory
        and broadcasts to SNS, while the concurrent racer receives 409 Conflict (advisory_already_published).
        """
        advisory = ThreatAdvisory.objects.create(
            created_by=analyst_user,
            title="Urgent Malware Alert",
            body="Be cautious of phishing attachments.",
            target_audience="GENERAL",
            category=ScamCategory.IMPERSONATION.value,
            severity=AdvisorySeverity.WARNING.value,
            status=AdvisoryStatus.DRAFT.value,
        )

        num_workers = 3
        results = []

        def publish_worker(worker_id):
            connection.close()
            try:
                adv = publish_advisory(advisory.id, analyst_user)
                return ("SUCCESS", adv.status)
            except ConflictError as e:
                return ("CONFLICT", e.detail)
            except Exception as e:
                return ("ERROR", str(e))
            finally:
                connection.close()

        with patch("apps.broadcasts.services.broadcast_service.client") as mock_client_factory:
            mock_sns = MagicMock()
            mock_sns.publish.return_value = {"MessageId": "mock-sns-msg-12345"}
            mock_client_factory.return_value = mock_sns

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(publish_worker, i) for i in range(num_workers)]
                for fut in as_completed(futures, timeout=15):
                    results.append(fut.result())

            # Assert exactly 1 SNS message was dispatched
            assert mock_sns.publish.call_count == 1, (
                f"Expected exactly 1 SNS publish call, got {mock_sns.publish.call_count}"
            )

        # Zero unexpected errors
        errors = [r for r in results if r[0] == "ERROR"]
        assert len(errors) == 0, f"Publish workers encountered unexpected errors: {errors}"

        statuses = [r[0] for r in results]
        # Exactly one worker succeeds, the others get 409 CONFLICT
        assert statuses.count("SUCCESS") == 1, f"Expected exactly 1 SUCCESS, got: {statuses}"
        assert statuses.count("CONFLICT") == num_workers - 1, f"Expected {num_workers - 1} CONFLICT, got: {statuses}"

        advisory.refresh_from_db()
        assert advisory.status == AdvisoryStatus.PUBLISHED.value
        assert advisory.published_by == analyst_user
        assert advisory.published_at is not None
