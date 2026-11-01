import io
import json
import uuid

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from moto import mock_aws
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.core import aws
from apps.ops.models import AuditEventType, SystemAuditLog
from apps.reports.models import (
    IndicatorType,
    PaymentMethod,
    Platform,
    ScamCategory,
    ScamReport,
)


def create_valid_test_png() -> bytes:
    bio = io.BytesIO()
    im = Image.new("RGB", (20, 20), color="blue")
    im.save(bio, format="PNG")
    return bio.getvalue()


def create_valid_test_jpeg() -> bytes:
    bio = io.BytesIO()
    im = Image.new("RGB", (20, 20), color="red")
    im.save(bio, format="JPEG")
    return bio.getvalue()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_citizen():
    user = User.objects.create_user(
        email="citizen_api@example.com",
        password="StrongPassword123!",
        role=Role.CITIZEN,
    )
    return user


@mock_aws
@pytest.mark.django_db
class TestReportOptionsAPI:
    def test_options_returns_200_and_expected_structure(self, api_client):
        response = api_client.get("/api/v1/reports/options/")
        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert "currencies" in data
        assert "categories" in data
        assert "platforms" in data
        assert "payment_methods" in data
        assert "indicator_types" in data
        assert "admin_areas" in data


@mock_aws
@pytest.mark.django_db
class TestReportCreateAPI:
    def setup_method(self, method=None):
        aws.reset_clients()
        s3 = aws.client("s3")
        s3.create_bucket(
            Bucket=settings.EVIDENCE_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        call_command("seed_playbooks")

    def test_anonymous_multipart_submission_with_2_files_returns_201(self, api_client):
        png_bytes = create_valid_test_png()
        jpeg_bytes = create_valid_test_jpeg()

        indicators_json = json.dumps([
            {"type": IndicatorType.URL, "value": "https://secure-login.phishing.test/auth"},
            {"type": IndicatorType.PHONE, "value": "0123456789"},
        ])

        data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.SMS,
            "message_text": "Your account is temporarily restricted. Please update your details.",
            "country_code": "MY",
            "currency": "MYR",
            "financial_loss": "0.00",
            "payment_method": PaymentMethod.NONE,
            "admin_area": "Selangor",
            "indicators": indicators_json,
            "evidence": [
                SimpleUploadedFile("screenshot1.png", png_bytes, content_type="image/png"),
                SimpleUploadedFile("screenshot2.jpg", jpeg_bytes, content_type="image/jpeg"),
            ],
        }

        response = api_client.post("/api/v1/reports/", data=data, format="multipart")
        assert response.status_code == 201
        res = response.json()

        assert "reference_code" in res
        assert res["reference_code"].startswith("SCM-")
        assert res["status"] == "PENDING"
        assert res["access_key"] is not None
        assert len(res["access_key"]) == 32
        assert "playbook" in res
        assert len(res["playbook"]["steps"]) > 0

        # Snapshot check: ensure no forbidden fields in public response per D68
        res_str = json.dumps(res)
        forbidden = [
            "raw_value", "ip_hash", "s3_key", "risk_score",
            "reporter_id", "message_text", "victim", "internal"
        ]
        for f in forbidden:
            assert f not in res_str

    def test_multipart_with_zero_evidence_files_returns_201(self, api_client):
        indicators_json = json.dumps([
            {"type": IndicatorType.PHONE, "value": "+60123456789"},
        ])
        data = {
            "category": ScamCategory.IMPERSONATION,
            "platform": Platform.WHATSAPP,
            "message_text": "Impersonator claiming to be government official.",
            "country_code": "MY",
            "currency": "MYR",
            "financial_loss": "0.00",
            "payment_method": PaymentMethod.NONE,
            "indicators": indicators_json,
        }
        response = api_client.post("/api/v1/reports/", data=data, format="multipart")
        assert response.status_code == 201
        assert response.json()["status"] == "PENDING"

    def test_multipart_with_3_evidence_files_succeeds(self, api_client):
        png_bytes = create_valid_test_png()
        indicators_json = json.dumps([{"type": IndicatorType.PHONE, "value": "0123456789"}])
        data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.EMAIL,
            "message_text": "Phishing test with max 3 files",
            "country_code": "MY",
            "currency": "MYR",
            "indicators": indicators_json,
            "evidence": [
                SimpleUploadedFile("f1.png", png_bytes, content_type="image/png"),
                SimpleUploadedFile("f2.png", png_bytes, content_type="image/png"),
                SimpleUploadedFile("f3.png", png_bytes, content_type="image/png"),
            ],
        }
        response = api_client.post("/api/v1/reports/", data=data, format="multipart")
        assert response.status_code == 201

    def test_multipart_with_4_evidence_files_returns_400(self, api_client):
        png_bytes = create_valid_test_png()
        indicators_json = json.dumps([{"type": IndicatorType.PHONE, "value": "0123456789"}])
        data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.EMAIL,
            "message_text": "Phishing test exceeding 3 files",
            "country_code": "MY",
            "currency": "MYR",
            "indicators": indicators_json,
            "evidence": [
                SimpleUploadedFile("f1.png", png_bytes, content_type="image/png"),
                SimpleUploadedFile("f2.png", png_bytes, content_type="image/png"),
                SimpleUploadedFile("f3.png", png_bytes, content_type="image/png"),
                SimpleUploadedFile("f4.png", png_bytes, content_type="image/png"),
            ],
        }
        response = api_client.post("/api/v1/reports/", data=data, format="multipart")
        assert response.status_code == 400
        assert "evidence" in response.json()["error"]["details"]

    def test_disguised_exe_file_returns_400(self, api_client):
        exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
        indicators_json = json.dumps([{"type": IndicatorType.PHONE, "value": "0123456789"}])
        data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.SMS,
            "message_text": "Executable file disguised as image",
            "country_code": "MY",
            "currency": "MYR",
            "indicators": indicators_json,
            "evidence": [
                SimpleUploadedFile("malware.png", exe_bytes, content_type="image/png"),
            ],
        }
        response = api_client.post("/api/v1/reports/", data=data, format="multipart")
        assert response.status_code == 400
        assert "evidence" in response.json()["error"]["details"]

    def test_invalid_idempotency_key_header_returns_400(self, api_client):
        indicators_json = json.dumps([{"type": IndicatorType.PHONE, "value": "0123456789"}])
        data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.SMS,
            "message_text": "Invalid idempotency key header test",
            "country_code": "MY",
            "currency": "MYR",
            "indicators": indicators_json,
        }
        response = api_client.post(
            "/api/v1/reports/",
            data=data,
            format="multipart",
            HTTP_IDEMPOTENCY_KEY="not-a-valid-uuid",
        )
        assert response.status_code == 400
        assert "Idempotency-Key" in response.json()["error"]["message"] or "Idempotency-Key" in str(response.json()["error"]["details"])

    def test_idempotency_replay_via_api_returns_200_and_omits_access_key(self, api_client):
        # D62: Replay returns 200 with same reference, no access key
        sub_key = str(uuid.uuid4())
        indicators_json = json.dumps([{"type": IndicatorType.PHONE, "value": "0123456789"}])
        data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.SMS,
            "message_text": "Idempotent submission narrative",
            "country_code": "MY",
            "currency": "MYR",
            "indicators": indicators_json,
        }

        # 1. First request -> 201
        res1 = api_client.post(
            "/api/v1/reports/",
            data=data,
            format="multipart",
            HTTP_IDEMPOTENCY_KEY=sub_key,
        )
        assert res1.status_code == 201
        body1 = res1.json()
        assert body1["access_key"] is not None

        # 2. Replay request -> 200
        res2 = api_client.post(
            "/api/v1/reports/",
            data=data,
            format="multipart",
            HTTP_IDEMPOTENCY_KEY=sub_key,
        )
        assert res2.status_code == 200
        body2 = res2.json()
        assert body2["reference_code"] == body1["reference_code"]
        assert body2["access_key"] is None

    def test_authenticated_citizen_submission_and_anonymous_flag(
        self, api_client, auth_citizen
    ):
        # D69: Valid token + anonymous=true leaves no link to user and report does NOT appear in mine
        api_client.force_authenticate(user=auth_citizen)

        # 1. Normal authenticated report
        ind_json = json.dumps([{"type": IndicatorType.EMAIL, "value": "scam@auth.test"}])
        res_auth = api_client.post(
            "/api/v1/reports/",
            data={
                "category": ScamCategory.ECOMMERCE_FRAUD,
                "platform": Platform.WEBSITE,
                "message_text": "Citizen authenticated report",
                "country_code": "MY",
                "currency": "MYR",
                "indicators": ind_json,
                "anonymous": False,
            },
            format="multipart",
        )
        assert res_auth.status_code == 201
        ref_auth = res_auth.json()["reference_code"]
        assert res_auth.json()["access_key"] is None

        # 2. Authenticated user files with anonymous=true
        res_anon = api_client.post(
            "/api/v1/reports/",
            data={
                "category": ScamCategory.ECOMMERCE_FRAUD,
                "platform": Platform.WEBSITE,
                "message_text": "Citizen anonymous report",
                "country_code": "MY",
                "currency": "MYR",
                "indicators": ind_json,
                "anonymous": True,
            },
            format="multipart",
        )
        assert res_anon.status_code == 201
        ref_anon = res_anon.json()["reference_code"]
        assert res_anon.json()["access_key"] is not None

        # 3. GET /reports/mine/ should show only ref_auth, NEVER ref_anon per D80
        mine_res = api_client.get("/api/v1/reports/mine/")
        assert mine_res.status_code == 200
        mine_refs = [r["reference_code"] for r in mine_res.json()["results"]]
        assert ref_auth in mine_refs
        assert ref_anon not in mine_refs

    def test_anonymous_submission_throttle_6th_attempt_returns_429(self, api_client):
        # D63: Anonymous 5 reports per ip_hash per hour; 6th returns 429
        ind_json = json.dumps([{"type": IndicatorType.PHONE, "value": "0123456789"}])
        data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.SMS,
            "message_text": "Throttling test message",
            "country_code": "MY",
            "currency": "MYR",
            "indicators": ind_json,
        }

        # Clear throttle history for this test by using dedicated IP
        headers = {"HTTP_X_FORWARDED_FOR": "203.0.113.195"}

        for i in range(5):
            res = api_client.post("/api/v1/reports/", data=data, format="multipart", **headers)
            assert res.status_code == 201, f"Attempt {i+1} failed with {res.status_code}"

        # 6th attempt
        res6 = api_client.post("/api/v1/reports/", data=data, format="multipart", **headers)
        assert res6.status_code == 429
        assert "Retry-After" in res6.headers

    @pytest.mark.parametrize(
        "ind_type,ind_value,expected_field",
        [
            (IndicatorType.PHONE, "invalid-phone", "phone"),
            (IndicatorType.URL, "ftp://invalid-scheme.test", "url"),
            (IndicatorType.EMAIL, "not-an-email", "email"),
            (IndicatorType.BANK_ACCOUNT, "not-digits", "bank_account"),
        ],
    )
    def test_invalid_indicators_return_400_no_s3_no_db_no_audit(
        self, api_client, ind_type, ind_value, expected_field
    ):
        png_bytes = create_valid_test_png()
        data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.SMS,
            "message_text": "Phishing test with invalid indicator",
            "country_code": "MY",
            "currency": "MYR",
            "financial_loss": "0.00",
            "payment_method": PaymentMethod.NONE,
            "admin_area": "Selangor",
            "indicators": json.dumps([{"type": ind_type, "value": ind_value}]),
            "evidence": [
                SimpleUploadedFile("proof.png", png_bytes, content_type="image/png"),
            ],
        }

        s3 = aws.client("s3")
        s3_before = s3.list_objects_v2(Bucket=settings.EVIDENCE_BUCKET).get("KeyCount", 0)
        reports_before = ScamReport.objects.count()
        audit_before = SystemAuditLog.objects.filter(
            event_type=AuditEventType.REPORT_SUBMITTED
        ).count()

        response = api_client.post("/api/v1/reports/", data=data, format="multipart")

        # Must return 400 validation_error (currently fails with 500)
        assert response.status_code == 400
        res_json = response.json()
        assert res_json["error"]["code"] == "validation_error"
        assert expected_field in res_json["error"]["details"]

        # Ensure no submitted raw value echoed in response
        assert ind_value not in json.dumps(res_json)

        # Ensure no S3 upload, no report, no audit log
        s3_after = s3.list_objects_v2(Bucket=settings.EVIDENCE_BUCKET).get("KeyCount", 0)
        assert s3_after == s3_before
        assert ScamReport.objects.count() == reports_before
        assert (
            SystemAuditLog.objects.filter(
                event_type=AuditEventType.REPORT_SUBMITTED
            ).count()
            == audit_before
        )

    def test_rate_limit_remote_addr_and_invalid_bypass(self, api_client):
        # 5 valid anonymous reports from one REMOTE_ADDR return 201, 6th returns 429
        # Invalid requests do not count toward the limit
        client_ip = "198.51.100.99"

        # Send 3 invalid indicator requests first
        for i in range(3):
            bad_data = {
                "category": ScamCategory.PHISHING,
                "platform": Platform.SMS,
                "message_text": "Invalid request attempt",
                "country_code": "MY",
                "currency": "MYR",
                "indicators": json.dumps([{"type": IndicatorType.PHONE, "value": f"bad-{i}"}]),
            }
            res_bad = api_client.post(
                "/api/v1/reports/",
                data=bad_data,
                format="multipart",
                REMOTE_ADDR=client_ip,
            )
            assert res_bad.status_code == 400

        # Send 5 valid anonymous reports
        valid_phones = [
            "+60123456781",
            "+60123456782",
            "+60123456783",
            "+60123456784",
            "+60123456785",
        ]
        for idx, phone in enumerate(valid_phones):
            good_data = {
                "category": ScamCategory.PHISHING,
                "platform": Platform.SMS,
                "message_text": f"Valid report narrative number {idx+1}",
                "country_code": "MY",
                "currency": "MYR",
                "indicators": json.dumps([{"type": IndicatorType.PHONE, "value": phone}]),
            }
            res_good = api_client.post(
                "/api/v1/reports/",
                data=good_data,
                format="multipart",
                REMOTE_ADDR=client_ip,
            )
            assert res_good.status_code == 201

        # 6th valid request from same REMOTE_ADDR must be throttled with 429 and Retry-After
        overflow_data = {
            "category": ScamCategory.PHISHING,
            "platform": Platform.SMS,
            "message_text": "6th report attempt exceeding limit",
            "country_code": "MY",
            "currency": "MYR",
            "indicators": json.dumps([{"type": IndicatorType.PHONE, "value": "+60123456786"}]),
        }
        res_overflow = api_client.post(
            "/api/v1/reports/",
            data=overflow_data,
            format="multipart",
            REMOTE_ADDR=client_ip,
        )
        assert res_overflow.status_code == 429
        assert "Retry-After" in res_overflow.headers


@mock_aws
@pytest.mark.django_db
class TestReportTrackAPI:
    def setup_method(self, method=None):
        aws.reset_clients()
        s3 = aws.client("s3")
        s3.create_bucket(
            Bucket=settings.EVIDENCE_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"},
        )
        call_command("seed_playbooks")

    def test_track_valid_report_returns_200_and_expected_fields(self, api_client):
        # Create anonymous report first
        ind_json = json.dumps([{"type": IndicatorType.PHONE, "value": "0123456789"}])
        create_res = api_client.post(
            "/api/v1/reports/",
            data={
                "category": ScamCategory.PHISHING,
                "platform": Platform.SMS,
                "message_text": "Track test report",
                "country_code": "MY",
                "currency": "MYR",
                "indicators": ind_json,
            },
            format="multipart",
        )
        ref_code = create_res.json()["reference_code"]
        access_key = create_res.json()["access_key"]

        # Track with access key
        track_res = api_client.post(
            "/api/v1/reports/track/",
            data={"reference_code": ref_code, "access_key": access_key},
            format="json",
        )
        assert track_res.status_code == 200
        data = track_res.json()
        assert data["reference_code"] == ref_code
        assert data["status"] == "PENDING"
        assert data["category"] == ScamCategory.PHISHING
        assert data["platform"] == Platform.SMS
        assert "playbook" in data

        # Snapshot test: verify no forbidden fields in public tracking response
        forbidden = ["message_text", "raw_value", "reporter", "ip_hash", "s3_key"]
        for f in forbidden:
            assert f not in json.dumps(data)

    def test_track_identical_404_for_unknown_reference_and_wrong_access_key(self, api_client):
        # D79: POST /reports/track/ never reveals existence differences
        ind_json = json.dumps([{"type": IndicatorType.PHONE, "value": "0123456789"}])
        create_res = api_client.post(
            "/api/v1/reports/",
            data={
                "category": ScamCategory.PHISHING,
                "platform": Platform.SMS,
                "message_text": "Report for track 404 test",
                "country_code": "MY",
                "currency": "MYR",
                "indicators": ind_json,
            },
            format="multipart",
        )
        existing_ref = create_res.json()["reference_code"]

        # 1. Unknown reference code
        res_unknown = api_client.post(
            "/api/v1/reports/track/",
            data={"reference_code": "SCM-2026-UNKNOWN1", "access_key": "some_random_access_key_12345"},
            format="json",
        )
        assert res_unknown.status_code == 404

        # 2. Existing reference with invalid access key
        res_wrong_key = api_client.post(
            "/api/v1/reports/track/",
            data={"reference_code": existing_ref, "access_key": "wrong_key_12345678901234567890"},
            format="json",
        )
        assert res_wrong_key.status_code == 404

        # Body comparison: error code, message, and structure must match identically (excluding request_id)
        err_unknown = res_unknown.json()["error"]
        err_wrong = res_wrong_key.json()["error"]
        assert err_unknown["code"] == err_wrong["code"] == "not_found"
        assert err_unknown["message"] == err_wrong["message"] == "Report not found."
        assert err_unknown["details"] == err_wrong["details"] is None

    def test_track_throttling_11th_failed_attempt_returns_429(self, api_client):
        # D79: 10 failures per ip_hash per 15 minutes then 429 with Retry-After
        headers = {"HTTP_X_FORWARDED_FOR": "203.0.113.210"}

        for i in range(10):
            res = api_client.post(
                "/api/v1/reports/track/",
                data={"reference_code": f"SCM-2026-FAIL{i:04d}", "access_key": "bad_key"},
                format="json",
                **headers,
            )
            assert res.status_code == 404

        # 11th attempt
        res11 = api_client.post(
            "/api/v1/reports/track/",
            data={"reference_code": "SCM-2026-FAIL0011", "access_key": "bad_key"},
            format="json",
            **headers,
        )
        assert res11.status_code == 429
        assert "Retry-After" in res11.headers


@pytest.mark.django_db
class TestMyReportsAPI:
    def test_mine_requires_authentication(self, api_client):
        res = api_client.get("/api/v1/reports/mine/")
        assert res.status_code == 401

    def test_mine_avoids_n_plus_one_queries(self, api_client, auth_citizen, django_assert_num_queries):
        api_client.force_authenticate(user=auth_citizen)

        # Create 1 report
        ScamReport.objects.create(
            reference_code="SCM-2026-NPLUS001",
            reporter=auth_citizen,
            is_anonymous=False,
            category=ScamCategory.PHISHING,
            platform=Platform.SMS,
            message_text="Test",
            country_code="MY",
            currency="MYR",
        )

        # Baseline query count
        with django_assert_num_queries(2):  # 1 for auth user / count, 1 for reports
            res1 = api_client.get("/api/v1/reports/mine/")
            assert res1.status_code == 200

        # Create 9 more reports
        for i in range(2, 11):
            ScamReport.objects.create(
                reference_code=f"SCM-2026-NPLUS{i:03d}",
                reporter=auth_citizen,
                is_anonymous=False,
                category=ScamCategory.PHISHING,
                platform=Platform.SMS,
                message_text="Test",
                country_code="MY",
                currency="MYR",
            )

        # Query count must remain identical (no N+1 queries)
        with django_assert_num_queries(2):
            res10 = api_client.get("/api/v1/reports/mine/")
            assert res10.status_code == 200
            assert len(res10.json()["results"]) == 10
