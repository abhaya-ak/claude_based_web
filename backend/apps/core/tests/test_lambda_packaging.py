import hashlib
import json
import sys
import zipfile
from pathlib import Path


def test_lambda_packager_creates_deterministic_zip_and_sha256():
    """D147: Verify package_lambda creates reproducible zip with fixed timestamps, valid SHA256, and under 50KB."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    backend_dir = repo_root / "backend"
    packager_script = backend_dir / "tools" / "package_lambda.py"
    zip_path = repo_root / "infra" / "lambda" / "heuristic_scanner.zip"
    sha_path = repo_root / "infra" / "lambda" / "heuristic_scanner.zip.sha256"

    assert packager_script.exists(), f"Packager script missing at {packager_script}"

    # Run packager module
    import subprocess

    result = subprocess.run(
        [sys.executable, str(packager_script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"package_lambda.py failed: {result.stderr}"

    assert zip_path.exists(), f"Lambda zip not created at {zip_path}"
    assert sha_path.exists(), f"Lambda sha256 not created at {sha_path}"

    # Verify size < 50 KB
    zip_bytes = zip_path.read_bytes()
    assert len(zip_bytes) < 50 * 1024, f"Zip artifact too large: {len(zip_bytes)} bytes"

    # Verify SHA256 integrity
    actual_sha = hashlib.sha256(zip_bytes).hexdigest()
    expected_sha = sha_path.read_text(encoding="utf-8").strip()
    assert actual_sha == expected_sha, f"SHA256 mismatch: {actual_sha} vs {expected_sha}"

    # Inspect zip contents
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "handler.py" in namelist, "handler.py missing from archive root"
        assert "scoring.py" in namelist, "scoring.py missing from archive root"
        # Ensure no tests or cache packaged
        assert not any("tests" in n for n in namelist)
        assert not any("__pycache__" in n for n in namelist)

        # Check deterministic timestamp (1980-01-01 00:00:00)
        for zinfo in zf.infolist():
            assert zinfo.date_time == (1980, 1, 1, 0, 0, 0), f"Timestamp not normalized on {zinfo.filename}"


def test_packaged_lambda_execution():
    """Verify loading and executing handler directly from the packaged zip archive."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    zip_path = repo_root / "infra" / "lambda" / "heuristic_scanner.zip"

    # Add zip to sys.path to simulate AWS Lambda execution environment
    zip_str = str(zip_path)
    if zip_str not in sys.path:
        sys.path.insert(0, zip_str)

    try:
        import handler

        # Call lambda_handler with test event formatted per Phase 5 spec
        event = {
            "report_id": "01J00000000000000000000000",
            "message_text": "Urgent payment required to claim inheritance from overseas escrow.",
            "indicators": [{"type": "URL", "host": "fake-scam-bank.top"}],
            "rules": {
                "KEYWORD": [
                    {"pattern": "urgent", "weight": 25},
                    {"pattern": "inheritance", "weight": 30},
                ],
                "TLD": [
                    {"pattern": ".top", "weight": 20},
                ],
                "SHORTENER": [],
            },
            "config": {
                "keyword_cap_points": 45,
            },
            "callback_url": None,  # no HTTP post during pure execution unit test
        }

        # Context mock with aws_request_id
        class DummyContext:
            aws_request_id = "test-req-12345"

        response = handler.lambda_handler(event, DummyContext())
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["report_id"] == "01J00000000000000000000000"
        assert body["risk_score"] == 65  # 45 (capped keywords) + 20 (tld .top)
        assert body["is_high_priority"] is False  # default threshold is 75
        assert body["lambda_request_id"] == "test-req-12345"
        assert len(body["breakdown"]) == 3
    finally:
        if zip_str in sys.path:
            sys.path.remove(zip_str)
