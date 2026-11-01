from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connections
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.tests.factories import UserFactory
from apps.core.jobs.registry import get_lock_id_for_job


@pytest.mark.django_db
class TestRunJobsAndAdvisoryLock:
    """TO BE PROVEN #4: Postgres advisory lock concurrency in run_jobs."""

    def test_flush_expired_tokens_job(self):
        user = UserFactory()
        now = timezone.now()

        # 1. Expired token (expires_at in past)
        expired_token = OutstandingToken.objects.create(
            user=user,
            jti="expired-jti-12345",
            token="expired-token-string",
            created_at=now - timedelta(days=10),
            expires_at=now - timedelta(days=3),
        )
        BlacklistedToken.objects.create(token=expired_token)

        # 2. Valid token (expires_at in future)
        valid_token = OutstandingToken.objects.create(
            user=user,
            jti="valid-jti-67890",
            token="valid-token-string",
            created_at=now,
            expires_at=now + timedelta(days=7),
        )

        out = StringIO()
        call_command("run_jobs", "--job", "flush_expired_tokens", stdout=out)

        # Expired token was deleted
        assert not OutstandingToken.objects.filter(id=expired_token.id).exists()
        assert not BlacklistedToken.objects.filter(token_id=expired_token.id).exists()

        # Valid token is preserved
        assert OutstandingToken.objects.filter(id=valid_token.id).exists()

    def test_advisory_lock_concurrency_skips_when_locked(self):
        """
        Prove TO BE PROVEN #4: When another worker holds pg_advisory_lock,
        run_jobs detects the lock, skips execution cleanly, and returns status skipped.
        """
        lock_id = get_lock_id_for_job("flush_expired_tokens")

        # Open a separate DB connection to simulate a concurrent worker session
        other_conn = connections.create_connection("default")
        try:
            with other_conn.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s);", [lock_id])
                acquired = cursor.fetchone()[0]
                assert acquired is True, "Failed to acquire test advisory lock on separate connection"

                try:
                    out = StringIO()
                    # Run the command while the lock is held by other_conn
                    call_command("run_jobs", "--job", "flush_expired_tokens", stdout=out)
                    output = out.getvalue()
                    assert "locked" in output.lower() or "skipped" in output.lower()
                finally:
                    cursor.execute("SELECT pg_advisory_unlock(%s);", [lock_id])
        finally:
            other_conn.close()

        # After releasing the lock, running again executes successfully
        out_after = StringIO()
        call_command("run_jobs", "--job", "flush_expired_tokens", stdout=out_after)
        output_after = out_after.getvalue()
        assert "completed" in output_after.lower() or "finished" in output_after.lower() or "success" in output_after.lower()

