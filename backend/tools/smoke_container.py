#!/usr/bin/env python3
"""
smoke_container.py — End-to-End Containerized Smoke Verification Suite (D151).

Tests live ScamShield backend endpoints over HTTP:
1. Health check (/api/v1/health/)
2. Readiness probe (/api/v1/health/ready/)
3. Citizen auth registration & login (/api/v1/auth/register/, /api/v1/auth/login/)
4. Scam report submission (/api/v1/reports/)
5. Public threat lookup (/api/v1/lookups/)
6. Spot-the-scam simulator attempt (/simulator/attempts/)
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class ContainerSmokeRunner:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.results = []

    def log(self, step: str, status: str, details: str = ""):
        msg = f"[{status.upper()}] {step}"
        if details:
            msg += f" - {details}"
        print(msg)
        self.results.append((step, status, details))

    def _request(self, method: str, path: str, data: dict = None, headers: dict = None) -> tuple[int, dict]:
        url = f"{self.base_url}{path}"
        req_headers = {"User-Agent": "ScamShield-SmokeRunner/1.0"}
        if self.token:
            req_headers["Authorization"] = f"Bearer {self.token}"
        if headers:
            req_headers.update(headers)

        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8")
                res_json = json.loads(raw) if raw else {}
                return status, res_json
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                res_json = json.loads(raw)
            except Exception:
                res_json = {"raw": raw}
            return e.code, res_json

    def run_all(self) -> bool:
        print(f"=== Starting ScamShield Smoke Runner against {self.base_url} ===")
        success = True

        # 1. Health check
        try:
            code, data = self._request("GET", "/api/v1/health/")
            if code == 200 and data.get("status") == "ok":
                self.log("1. System Health Probe", "PASS", f"HTTP {code} status={data.get('status')}")
            else:
                self.log("1. System Health Probe", "FAIL", f"HTTP {code} data={data}")
                success = False
        except Exception as e:
            self.log("1. System Health Probe", "FAIL", str(e))
            success = False

        # 2. Readiness check
        try:
            code, data = self._request("GET", "/api/v1/health/ready/")
            if code == 200 and data.get("database") == "ok":
                self.log("2. Database Readiness Probe", "PASS", f"HTTP {code} db={data.get('database')}")
            else:
                self.log("2. Database Readiness Probe", "FAIL", f"HTTP {code} data={data}")
                success = False
        except Exception as e:
            self.log("2. Database Readiness Probe", "FAIL", str(e))
            success = False

        # 3. User registration & login
        unique_id = int(time.time())
        test_email = f"smoke_user_{unique_id}@scamshield.test"
        test_pwd = "P@ssword12345!Secure"

        try:
            reg_code, reg_data = self._request("POST", "/api/v1/auth/register/", {
                "email": test_email,
                "password": test_pwd,
                "full_name": "Smoke Test Citizen",
                "phone_number": "+977-9800000000",
            })
            if reg_code == 201:
                self.log("3a. Citizen Registration", "PASS", f"HTTP {reg_code}")
            else:
                self.log("3a. Citizen Registration", "FAIL", f"HTTP {reg_code} data={reg_data}")
                success = False

            # Login to get JWT
            login_code, login_data = self._request("POST", "/api/v1/auth/login/", {
                "email": test_email,
                "password": test_pwd,
            })
            if login_code == 200 and "access" in login_data:
                self.token = login_data["access"]
                self.log("3b. Citizen Login", "PASS", f"HTTP {login_code} token acquired")
            else:
                self.log("3b. Citizen Login", "FAIL", f"HTTP {login_code} data={login_data}")
                success = False
        except Exception as e:
            self.log("3. User Authentication", "FAIL", str(e))
            success = False

        # 4. Scam report submission
        try:
            boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
            indicators_json = json.dumps([
                {"type": "PHONE", "value": "+9779812345678"},
                {"type": "URL", "value": "https://crypto-doubler.top"},
            ])
            form_fields = {
                "category": "PHISHING",
                "platform": "WHATSAPP",
                "message_text": "Guaranteed 500% weekly returns on crypto trading bot investment scheme.",
                "country_code": "NP",
                "currency": "NPR",
                "financial_loss": "0.00",
                "payment_method": "NONE",
                "indicators": indicators_json,
            }
            body_parts = []
            for k, v in form_fields.items():
                body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
            body_parts.append(f"--{boundary}--\r\n".encode())
            multipart_body = b"".join(body_parts)

            url = f"{self.base_url}/api/v1/reports/"
            idem_key = str(uuid.uuid4())
            req = urllib.request.Request(url, data=multipart_body, headers={
                "User-Agent": "ScamShield-SmokeRunner/1.0",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Idempotency-Key": idem_key,
            }, method="POST")

            with urllib.request.urlopen(req, timeout=10) as resp:
                rep_code = resp.status
                rep_data = json.loads(resp.read().decode("utf-8"))

            if rep_code == 201 and "reference_code" in rep_data:
                self.log("4. Scam Report Submission", "PASS", f"HTTP {rep_code} reference={rep_data.get('reference_code')}")
            else:
                self.log("4. Scam Report Submission", "FAIL", f"HTTP {rep_code} data={rep_data}")
                success = False
        except Exception as e:
            self.log("4. Scam Report Submission", "FAIL", str(e))
            success = False

        # 5. Public threat lookup
        try:
            lookup_code, lookup_data = self._request("POST", "/api/v1/lookups/", {
                "query": "crypto-doubler.top"
            })
            if lookup_code == 200 and "verdict" in lookup_data:
                self.log("5. Public Threat Lookup", "PASS", f"HTTP {lookup_code} verdict={lookup_data.get('verdict')}")
            else:
                self.log("5. Public Threat Lookup", "FAIL", f"HTTP {lookup_code} data={lookup_data}")
                success = False
        except Exception as e:
            self.log("5. Public Threat Lookup", "FAIL", str(e))
            success = False

        # 6. Simulator attempt creation
        try:
            sim_code, sim_data = self._request("POST", "/api/v1/simulator/attempts/", {})
            if sim_code == 201 or sim_code == 200:
                self.log("6. Simulator Attempt Init", "PASS", f"HTTP {sim_code}")
            else:
                self.log("6. Simulator Attempt Init", "FAIL", f"HTTP {sim_code} data={sim_data}")
                success = False
        except Exception as e:
            self.log("6. Simulator Attempt Init", "FAIL", str(e))
            success = False

        print("\n=== Smoke Verification Summary ===")
        passes = sum(1 for _, s, _ in self.results if s == "PASS")
        total = len(self.results)
        print(f"Passed: {passes}/{total}")

        return success


if __name__ == "__main__":
    target_url = "http://127.0.0.1:8000"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--base-url", "-u", "-BaseUrl") and i + 1 < len(args):
            target_url = args[i + 1]
            i += 2
        elif not arg.startswith("-"):
            target_url = arg
            i += 1
        else:
            i += 1

    runner = ContainerSmokeRunner(target_url)
    ok = runner.run_all()
    sys.exit(0 if ok else 1)
