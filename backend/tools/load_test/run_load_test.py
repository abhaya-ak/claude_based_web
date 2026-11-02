#!/usr/bin/env python3
"""
tools/load_test/run_load_test.py
Standalone standard-library Python multi-threaded load test runner (D141).
Executes the Phase 12 load scenario mix:
- 70% threat lookups (POST /api/v1/lookups/)
- 20% literacy hub browse (GET /api/v1/guides/)
- 8% report submissions (POST /api/v1/reports/)
- 2% spot-the-scam simulator attempt (POST /api/v1/simulator/attempts/)

Collects:
- Total requests
- Status counts (2xx, 429 throttled, 4xx, 5xx)
- Request latency percentiles: p50, p90, p95, p99, max
- Emits raw JSON output and can format a Markdown summary table for docs/load-test-report.md.
"""

import argparse
import json
import math
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ResultRecord:
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    is_throttle: bool
    is_error: bool
    error_message: str | None = None


@dataclass
class ScenarioMetrics:
    total_requests: int = 0
    successful_requests: int = 0
    throttled_429: int = 0
    client_errors_4xx: int = 0
    server_errors_5xx: int = 0
    latencies_ms: list[float] = field(default_factory=list)


SAMPLE_INDICATORS = [
    {"type": "PHONE", "value": "+60123456789"},
    {"type": "URL", "value": "https://secure-maybank-login.com/auth"},
    {"type": "DOMAIN", "value": "cimb-verify-alert.com"},
    {"type": "EMAIL", "value": "urgent-notice@support-bank-my.com"},
    {"type": "BANK_ACCOUNT", "value": "123456789012"},
    {"type": "PHONE", "value": "+60198765432"},
    {"type": "URL", "value": "https://epf-withdrawal-bonus.online"},
]


def execute_request(base_url: str, user_id: int) -> ResultRecord:
    # 70% lookup, 20% hub browse, 8% report submit, 2% simulator
    roll = random.random()
    ip_address = f"198.51.100.{(user_id % 250) + 1}"
    headers = {
        "User-Agent": f"ScamShieldLoadTestWorker/{user_id}",
        "X-Forwarded-For": ip_address,
        "Accept": "application/json",
    }

    start_time = time.perf_counter()
    endpoint = ""
    method = "GET"
    req = None

    try:
        if roll < 0.70:
            endpoint = "/api/v1/lookups/"
            method = "POST"
            target = random.choice(SAMPLE_INDICATORS)
            payload = json.dumps({"query": target["value"]}).encode("utf-8")
            headers["Content-Type"] = "application/json"
            req = urllib.request.Request(
                f"{base_url}{endpoint}",
                data=payload,
                headers=headers,
                method="POST",
            )
        elif roll < 0.90:
            endpoint = "/api/v1/guides/"
            method = "GET"
            query_params = urllib.parse.urlencode({"language": "EN", "limit": 10})
            req = urllib.request.Request(
                f"{base_url}{endpoint}?{query_params}",
                headers=headers,
                method="GET",
            )
        elif roll < 0.98:
            endpoint = "/api/v1/reports/"
            method = "POST"
            ind = random.choice(SAMPLE_INDICATORS)
            report_data = {
                "client_submission_id": f"load-{user_id}-{int(time.time() * 1000)}-{random.randint(1000, 9999)}",
                "category": "PHISHING",
                "platform": "WHATSAPP",
                "country_code": "MY",
                "currency": "MYR",
                "financial_loss": "0.00",
                "payment_method": "NONE",
                "message_text": f"Simulated load test scam message submission from worker {user_id}.",
                "indicators": [ind],
            }
            payload = json.dumps(report_data).encode("utf-8")
            headers["Content-Type"] = "application/json"
            req = urllib.request.Request(
                f"{base_url}{endpoint}",
                data=payload,
                headers=headers,
                method="POST",
            )
        else:
            endpoint = "/api/v1/simulator/attempts/"
            method = "POST"
            payload = json.dumps({"difficulty": "BEGINNER"}).encode("utf-8")
            headers["Content-Type"] = "application/json"
            req = urllib.request.Request(
                f"{base_url}{endpoint}",
                data=payload,
                headers=headers,
                method="POST",
            )

        with urllib.request.urlopen(req, timeout=15) as resp:
            status_code = resp.status
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ResultRecord(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                is_throttle=(status_code == 429),
                is_error=(status_code >= 400 and status_code != 429),
            )

    except urllib.error.HTTPError as he:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return ResultRecord(
            endpoint=endpoint,
            method=method,
            status_code=he.code,
            duration_ms=duration_ms,
            is_throttle=(he.code == 429),
            is_error=(he.code >= 400 and he.code != 429),
            error_message=str(he.reason),
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return ResultRecord(
            endpoint=endpoint,
            method=method,
            status_code=0,
            duration_ms=duration_ms,
            is_throttle=False,
            is_error=True,
            error_message=str(exc),
        )


def calculate_percentile(sorted_list: list[float], percentile: float) -> float:
    if not sorted_list:
        return 0.0
    k = (len(sorted_list) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_list[int(k)]
    d0 = sorted_list[int(f)] * (c - k)
    d1 = sorted_list[int(c)] * (k - f)
    return d0 + d1


def run_benchmark(
    base_url: str,
    concurrency: int,
    total_requests: int,
    duration_seconds: int | None = None,
) -> dict:
    results: list[ResultRecord] = []
    start_global = time.perf_counter()
    completed_requests = 0

    print(f"Starting load test on {base_url} (concurrency={concurrency}, target_requests={total_requests})...")

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = set()
        user_counter = 0

        # Prime initial tasks
        for _ in range(concurrency):
            user_counter += 1
            futures.add(executor.submit(execute_request, base_url, user_counter))

        while futures and (completed_requests < total_requests):
            if duration_seconds and (time.perf_counter() - start_global > duration_seconds):
                break

            for future in as_completed(futures):
                futures.remove(future)
                rec = future.result()
                results.append(rec)
                completed_requests += 1

                if completed_requests % 50 == 0:
                    elapsed = time.perf_counter() - start_global
                    rps = completed_requests / elapsed if elapsed > 0 else 0
                    print(f"Progress: {completed_requests}/{total_requests} ({rps:.1f} req/s)")

                if completed_requests < total_requests:
                    user_counter += 1
                    futures.add(executor.submit(execute_request, base_url, user_counter))
                break

    total_elapsed = time.perf_counter() - start_global

    by_endpoint: dict[str, ScenarioMetrics] = {}
    overall = ScenarioMetrics()

    for r in results:
        ep = r.endpoint or "unknown"
        if ep not in by_endpoint:
            by_endpoint[ep] = ScenarioMetrics()

        metric = by_endpoint[ep]
        for m in (metric, overall):
            m.total_requests += 1
            m.latencies_ms.append(r.duration_ms)
            if r.status_code == 429:
                m.throttled_429 += 1
            elif 200 <= r.status_code < 300:
                m.successful_requests += 1
            elif 400 <= r.status_code < 500:
                m.client_errors_4xx += 1
            elif r.status_code >= 500 or r.status_code == 0:
                m.server_errors_5xx += 1

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "concurrency": concurrency,
        "total_requests": len(results),
        "total_elapsed_seconds": round(total_elapsed, 2),
        "requests_per_second": round(len(results) / total_elapsed, 2) if total_elapsed > 0 else 0,
        "overall": {
            "total": overall.total_requests,
            "success_2xx": overall.successful_requests,
            "throttled_429": overall.throttled_429,
            "client_error_4xx": overall.client_errors_4xx,
            "server_error_5xx": overall.server_errors_5xx,
            "error_rate_pct": round((overall.server_errors_5xx / max(1, overall.total_requests)) * 100, 2),
            "p50_ms": round(calculate_percentile(sorted(overall.latencies_ms), 50), 2),
            "p90_ms": round(calculate_percentile(sorted(overall.latencies_ms), 90), 2),
            "p95_ms": round(calculate_percentile(sorted(overall.latencies_ms), 95), 2),
            "p99_ms": round(calculate_percentile(sorted(overall.latencies_ms), 99), 2),
            "max_ms": round(max(overall.latencies_ms) if overall.latencies_ms else 0, 2),
        },
        "endpoints": {},
    }

    for ep, m in by_endpoint.items():
        sorted_l = sorted(m.latencies_ms)
        summary["endpoints"][ep] = {
            "total": m.total_requests,
            "success_2xx": m.successful_requests,
            "throttled_429": m.throttled_429,
            "client_error_4xx": m.client_errors_4xx,
            "server_error_5xx": m.server_errors_5xx,
            "p50_ms": round(calculate_percentile(sorted_l, 50), 2),
            "p95_ms": round(calculate_percentile(sorted_l, 95), 2),
            "p99_ms": round(calculate_percentile(sorted_l, 99), 2),
        }

    return summary


def main():
    parser = argparse.ArgumentParser(description="ScamShield Cloud Performance Benchmarking Runner")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of ScamShield API")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent virtual user threads")
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests to execute")
    parser.add_argument("--duration", type=int, default=None, help="Maximum duration in seconds")
    parser.add_argument("--out-json", default="docs/load-test-metrics.json", help="Path to save raw JSON metrics")

    args = parser.parse_args()
    summary = run_benchmark(
        base_url=args.url.rstrip("/"),
        concurrency=args.concurrency,
        total_requests=args.requests,
        duration_seconds=args.duration,
    )

    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n================== LOAD TEST BENCHMARK RESULTS ==================")
    print(f"Total Requests:       {summary['total_requests']}")
    print(f"Elapsed Time:         {summary['total_elapsed_seconds']}s")
    print(f"Throughput:           {summary['requests_per_second']} req/s")
    print(f"Success (2xx):        {summary['overall']['success_2xx']}")
    print(f"Throttled (429):      {summary['overall']['throttled_429']}")
    print(f"Server Errors (5xx):  {summary['overall']['server_error_5xx']} (Error Rate: {summary['overall']['error_rate_pct']}%)")
    print(f"p50 Latency:          {summary['overall']['p50_ms']} ms")
    print(f"p95 Latency:          {summary['overall']['p95_ms']} ms")
    print(f"p99 Latency:          {summary['overall']['p99_ms']} ms")
    print(f"Max Latency:          {summary['overall']['max_ms']} ms")
    print("=================================================================\n")


if __name__ == "__main__":
    main()
