import time
from pathlib import Path

import pytest
from django.test import Client


@pytest.mark.django_db
def test_pinned_lockfiles_exist_and_strictly_pinned():
    """D39: Assert base.lock.txt and dev.lock.txt exist and every dependency is pinned with =="""
    base_lock = Path("requirements/base.lock.txt")
    dev_lock = Path("requirements/dev.lock.txt")

    assert base_lock.exists(), "requirements/base.lock.txt must exist"
    assert dev_lock.exists(), "requirements/dev.lock.txt must exist"

    base_lines = [
        line.strip()
        for line in base_lock.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    dev_lines = [
        line.strip()
        for line in dev_lock.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert len(base_lines) >= 20, f"Expected at least 20 pinned base packages, got {len(base_lines)}"
    assert len(dev_lines) >= 40, f"Expected at least 40 pinned dev packages, got {len(dev_lines)}"

    for line in base_lines:
        assert "==" in line, f"Line in base.lock.txt is not strictly pinned: {line}"
        assert not line.startswith("-r "), f"base.lock.txt should be fully unrolled: {line}"

    for line in dev_lines:
        assert "==" in line, f"Line in dev.lock.txt is not strictly pinned: {line}"


def test_dockerfile_hardening_specifications():
    """D146: Assert Dockerfile adheres to security standards: python:3.13-slim, base.lock.txt, non-root, healthcheck."""
    dockerfile = Path("Dockerfile")
    assert dockerfile.exists(), "Dockerfile must exist"
    content = dockerfile.read_text(encoding="utf-8")

    assert "python:3.13-slim" in content, "Dockerfile must use python:3.13-slim"
    assert "requirements/base.lock.txt" in content, "Dockerfile must install from requirements/base.lock.txt"
    assert "useradd -m -u 1000" in content, "Dockerfile must create appuser with UID 1000"
    assert "USER appuser" in content, "Dockerfile must run as non-root USER appuser"
    assert "EXPOSE 8000" in content, "Dockerfile must expose port 8000"
    assert "HEALTHCHECK" in content, "Dockerfile must declare HEALTHCHECK instruction"
    assert "http://127.0.0.1:8000/api/v1/health/" in content, "HEALTHCHECK must probe /api/v1/health/"


def test_dockerignore_excludes_sensitive_and_dev_artifacts():
    """Assert .dockerignore excludes virtualenvs, test caches, .env files, docs, and git data."""
    dockerignore = Path(".dockerignore")
    assert dockerignore.exists(), ".dockerignore must exist"
    content = dockerignore.read_text(encoding="utf-8").splitlines()
    entries = {line.strip() for line in content if line.strip() and not line.strip().startswith("#")}

    required_patterns = {".git", ".venv", ".pytest_cache", ".ruff_cache", ".env", "docs"}
    for pattern in required_patterns:
        assert pattern in entries or any(pattern in e for e in entries), f"Missing {pattern} in .dockerignore"


@pytest.mark.django_db
def test_to_be_proven_26_healthcheck_probe_latency_and_zero_db():
    """TO BE PROVEN #26: /api/v1/health/ must respond within 200ms and execute 0 database queries."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    client = Client()

    # Warm-up request
    client.get("/api/v1/health/")

    # Measure latency and db query count
    with CaptureQueriesContext(connection) as queries:
        start_time = time.perf_counter()
        response = client.get("/api/v1/health/")
        duration_ms = (time.perf_counter() - start_time) * 1000

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert duration_ms < 200.0, f"Healthcheck exceeded 200ms latency: {duration_ms:.2f}ms"
    assert len(queries) == 0, f"Healthcheck executed {len(queries)} DB queries; expected 0"
