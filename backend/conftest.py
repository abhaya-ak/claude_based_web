import pytest
from django.db.backends.base.creation import BaseDatabaseCreation

# Ensure any lingering test database connections are closed/terminated before DROP DATABASE
_orig_destroy_test_db = BaseDatabaseCreation._destroy_test_db


def _clean_destroy_test_db(self, test_database_name, verbosity):
    from django.db import connections

    connections.close_all()
    try:
        with self._nodb_cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid();
            """,
                [test_database_name],
            )
    except Exception:
        pass
    return _orig_destroy_test_db(self, test_database_name, verbosity)


BaseDatabaseCreation._destroy_test_db = _clean_destroy_test_db


@pytest.fixture(autouse=True)
def _block_aws_network(monkeypatch):
    """Safety fixture: sets dummy AWS credentials and disables IMDS to prevent accidental AWS calls."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-1")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)
    monkeypatch.delenv("AWS_ENDPOINT_URL_SNS", raising=False)
    monkeypatch.delenv("AWS_ENDPOINT_URL_CLOUDWATCH", raising=False)
