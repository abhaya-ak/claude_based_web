import io
from pathlib import Path

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_openapi_schema_matches_committed_file():
    out = io.StringIO()
    call_command("spectacular", "--validate", stdout=out)
    generated = out.getvalue().strip().replace("\r\n", "\n")

    schema_path = Path(__file__).resolve().parent.parent.parent.parent / "openapi.yaml"
    assert schema_path.exists(), "openapi.yaml must exist in backend directory"

    with open(schema_path, encoding="utf-8") as f:
        committed = f.read().strip().replace("\r\n", "\n")

    assert generated == committed, (
        "OpenAPI schema has drifted from openapi.yaml. "
        "Run `python manage.py spectacular --file openapi.yaml --validate`."
    )
