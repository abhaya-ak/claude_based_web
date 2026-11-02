import re
import subprocess
from pathlib import Path

from django.conf import settings

FORBIDDEN_FILE_PATTERNS = [
    re.compile(r"(^|/)\.env(\.[^/]+)?$"),  # .env or .env.local, but NOT .env.example
    re.compile(r"\.(pem|p12|pfx|tfstate(\.backup)?)$", re.IGNORECASE),
    re.compile(r"(^|/)id_rsa(\.pub)?$", re.IGNORECASE),
    re.compile(r"(^|/)local_settings\.py$", re.IGNORECASE),
    re.compile(r"(^|/)credentials\.json$", re.IGNORECASE),
]

# Patterns for secrets inside file contents
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
AWS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
AWS_SECRET_PATTERN = re.compile(r"aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]", re.IGNORECASE)

SAFE_MOCK_AWS_KEYS = {
    "AKIAIOSFODNN7EXAMPLE",
    "ASIAIOSFODNN7EXAMPLE",
}


def _get_tracked_files():
    """Retrieve all files tracked by git in the repository."""
    repo_root = Path(settings.BASE_DIR).parent
    proc = subprocess.run(  # noqa: S603, S607
        ["git", "ls-files"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def test_no_secret_files_committed_to_git():
    """
    D142 / OWASP: Ensure no private keys, .env secrets, or state files are checked into git.
    """
    tracked_files = _get_tracked_files()
    assert len(tracked_files) > 50, "Expected git ls-files to return tracked repository files"

    for filepath in tracked_files:
        norm_path = filepath.replace("\\", "/")
        if norm_path.endswith(".env.example"):
            continue
        for pattern in FORBIDDEN_FILE_PATTERNS:
            assert not pattern.search(norm_path), (
                f"Tracked file '{filepath}' matches forbidden sensitive file pattern {pattern.pattern}"
            )


def test_tracked_files_contain_no_private_keys_or_aws_secrets():
    """
    D142 / OWASP: Grep/scan tracked text files ensuring no hardcoded AWS credentials or private keys.
    """
    repo_root = Path(settings.BASE_DIR).parent
    tracked_files = _get_tracked_files()

    for rel_path in tracked_files:
        # Skip this test file itself to avoid self-match on regex definitions
        if "test_secrets_scan.py" in rel_path:
            continue

        full_path = repo_root / rel_path
        if not full_path.is_file():
            continue

        # Skip binary files, lockfiles, or large generated fixtures
        if any(rel_path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2", ".pdf")):
            continue

        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        # 1. Private keys
        assert not PRIVATE_KEY_PATTERN.search(content), (
            f"File '{rel_path}' contains private key header"
        )

        # 2. AWS Access Key IDs
        for match in AWS_KEY_PATTERN.findall(content):
            assert match in SAFE_MOCK_AWS_KEYS, (
                f"File '{rel_path}' contains potentially live AWS Access Key ID: {match}"
            )

        # 3. AWS Secret Access Keys
        assert not AWS_SECRET_PATTERN.search(content), (
            f"File '{rel_path}' contains hardcoded AWS Secret Access Key assignment"
        )


def test_gitignore_ignores_critical_sensitive_patterns():
    """
    Ensure root .gitignore explicitly includes .env, *.pem, *.key, and local configs.
    """
    repo_root = Path(settings.BASE_DIR).parent
    gitignore_path = repo_root / ".gitignore"
    assert gitignore_path.exists(), "Root .gitignore must exist"

    content = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in content, ".gitignore must ignore .env files"
    assert "*.pem" in content or "*.key" in content, ".gitignore must ignore key/certificate files"
