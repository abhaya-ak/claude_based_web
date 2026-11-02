"""
Phase 12 Load & Latency Performance Test Suite (D141).
Executes automated client benchmarking on core read/write endpoints and asserts
that p95 latencies meet the university CLO2 criteria (<300ms for lookup, <500ms for queue/analytics).
"""

import time
import uuid

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ApprovalStatus, Role, User
from apps.intel.models import IndicatorStatus, ThreatLevel, VerifiedIndicator
from apps.reports.models import IndicatorType, Platform, ScamCategory, ScamReport


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    user = User.objects.create_user(
        email="perf_analyst@scamshield.test",
        password="ValidPassword123!",
        role=Role.ANALYST,
        approval_status=ApprovalStatus.APPROVED,
    )
    return user


@pytest.mark.django_db
def test_public_threat_lookup_p95_latency(api_client, analyst_user):
    """
    Public lookup benchmark:
    Tests repeated queries on indexed verified indicators and asserts p95 latency is under 300ms.
    """
    now = timezone.now()
    indicators = [
        VerifiedIndicator(
            type=IndicatorType.PHONE.value,
            normalized_value=f"+6012345{i:04d}",
            display_value=f"+60 12-345 {i:04d}",
            primary_category=ScamCategory.PHISHING.value,
            threat_level=ThreatLevel.MEDIUM.value if i % 2 == 0 else ThreatLevel.HIGH.value,
            total_report_count=5,
            first_seen_at=now,
            last_seen_at=now,
            verified_at=now,
            status=IndicatorStatus.ACTIVE.value,
            verified_by=analyst_user,
        )
        for i in range(100)
    ]
    VerifiedIndicator.objects.bulk_create(indicators)

    # Warmup query
    api_client.post(
        "/api/v1/lookups/",
        data={"query": "+60123450000"},
        format="json",
        REMOTE_ADDR="198.51.100.254", HTTP_X_FORWARDED_FOR="198.51.100.254",
    )

    latencies = []
    # Execute 30 lookups across distinct IPs to bypass throttling
    for i in range(30):
        client_ip = f"198.51.100.{(i % 250) + 1}"
        query_val = f"+6012345{i:04d}"
        t0 = time.perf_counter()
        resp = api_client.post(
            "/api/v1/lookups/",
            data={"query": query_val},
            format="json",
            REMOTE_ADDR=client_ip, HTTP_X_FORWARDED_FOR=client_ip,
        )
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        assert resp.status_code == status.HTTP_200_OK

    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95_latency = latencies[p95_index]
    print(f"\n[BENCHMARK] Threat Lookup p95 Latency: {p95_latency:.2f} ms")
    assert p95_latency < 300.0, f"Lookup p95 latency {p95_latency:.2f}ms exceeds target 300ms"


@pytest.mark.django_db
def test_triage_queue_p95_latency(api_client, analyst_user):
    """
    Analyst triage queue benchmark:
    Tests queue aggregation and filtering across 100 reports and asserts p95 latency is under 500ms.
    """
    reports = [
        ScamReport(
            reference_code=f"SCM-PERF-{i:04d}",
            client_submission_id=uuid.uuid4(),
            category=ScamCategory.PHISHING.value,
            platform=Platform.WHATSAPP.value,
            status="PENDING",
            country_code="MY",
            currency="MYR",
            financial_loss="100.00",
        )
        for i in range(100)
    ]
    ScamReport.objects.bulk_create(reports)

    api_client.force_authenticate(user=analyst_user)

    # Warmup query
    api_client.get("/api/v1/triage/queue/?status=PENDING&page_size=20")

    latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        resp = api_client.get("/api/v1/triage/queue/?status=PENDING&page_size=20")
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        assert resp.status_code == status.HTTP_200_OK

    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95_latency = latencies[p95_index]
    print(f"\n[BENCHMARK] Triage Queue p95 Latency: {p95_latency:.2f} ms")
    assert p95_latency < 500.0, f"Triage queue p95 latency {p95_latency:.2f}ms exceeds target 500ms"


@pytest.mark.django_db
def test_analytics_volume_p95_latency(api_client, analyst_user):
    """
    Analytics aggregations benchmark:
    Tests analytics volume grouping over 30d and asserts p95 latency is under 500ms.
    """
    api_client.force_authenticate(user=analyst_user)

    # Warmup query (loads Django ORM models / DB connection pool)
    api_client.get("/api/v1/analytics/volume/?range=30d")

    latencies = []
    for _ in range(20):
        t0 = time.perf_counter()
        resp = api_client.get("/api/v1/analytics/volume/?range=30d")
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        assert resp.status_code == status.HTTP_200_OK

    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95_latency = latencies[p95_index]
    print(f"\n[BENCHMARK] Analytics Volume p95 Latency: {p95_latency:.2f} ms")
    assert p95_latency < 500.0, f"Analytics volume p95 latency {p95_latency:.2f}ms exceeds target 500ms"
