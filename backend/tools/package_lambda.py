#!/usr/bin/env python3
"""
package_lambda.py — Deterministic packager for Heuristic Scanner Lambda (D147).

Builds reproducible zip archive with normalized file permissions and fixed timestamps (1980-01-01 00:00:00).
Generates SHA256 companion digest file for Terraform / CloudFormation verification.
"""

import hashlib
import io
import zipfile
from pathlib import Path


def package_heuristic_scanner(repo_root: Path = None) -> tuple[Path, str]:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent

    source_dir = repo_root / "backend" / "lambda" / "heuristic_scanner"
    out_dir = repo_root / "infra" / "lambda"
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_file_path = out_dir / "heuristic_scanner.zip"
    sha_file_path = out_dir / "heuristic_scanner.zip.sha256"

    # Files to include at root of zip
    include_files = [
        ("handler.py", source_dir / "handler.py"),
        ("scoring.py", source_dir / "scoring.py"),
    ]

    for _name, p in include_files:
        if not p.exists():
            raise FileNotFoundError(f"Required Lambda source missing: {p}")

    # Create deterministic zip in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Sort files for deterministic entry ordering
        for arcname, file_path in sorted(include_files, key=lambda x: x[0]):
            content = file_path.read_bytes()
            # Normalize line endings to LF for cross-platform reproducibility
            content = content.replace(b"\r\n", b"\n")

            zinfo = zipfile.ZipInfo(filename=arcname, date_time=(1980, 1, 1, 0, 0, 0))
            # Set readable/executable unix permissions: 0o644 (-rw-r--r--)
            zinfo.external_attr = 0o644 << 16
            zf.writestr(zinfo, content)

    zip_bytes = zip_buffer.getvalue()

    # Write zip file
    zip_file_path.write_bytes(zip_bytes)

    # Compute SHA256
    sha256_hash = hashlib.sha256(zip_bytes).hexdigest()
    sha_file_path.write_text(sha256_hash + "\n", encoding="utf-8")

    return zip_file_path, sha256_hash


if __name__ == "__main__":
    zip_path, digest = package_heuristic_scanner()
    print(f"Packaged Lambda: {zip_path} ({len(zip_path.read_bytes())} bytes)")
    print(f"SHA256: {digest}")
