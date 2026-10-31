from pathlib import Path

import yaml
from django.conf import settings
from django.test import Client, override_settings
from drf_spectacular.generators import SchemaGenerator

OPENAPI_PATH = Path(settings.BASE_DIR).parent / "docs" / "openapi.yaml"


class TestOpenApiSchemaAndDrift:
    """Verify OpenAPI schema generation, repo committed file drift, and docs UI toggle (D37)."""

    def test_openapi_file_exists_and_is_valid_yaml(self):
        assert OPENAPI_PATH.exists(), f"docs/openapi.yaml not found at {OPENAPI_PATH}"
        content = OPENAPI_PATH.read_text(encoding="utf-8")
        assert "\r\n" not in content, "docs/openapi.yaml must use LF (\\n) line endings, not CRLF"
        data = yaml.safe_load(content)
        assert isinstance(data, dict)
        assert data.get("openapi", "").startswith("3.")
        assert data.get("info", {}).get("title") == "ScamShield API"

    def test_schema_generator_matches_committed_yaml(self):
        generator = SchemaGenerator()
        live_schema = generator.get_schema(request=None, public=True)
        assert live_schema is not None

        content = OPENAPI_PATH.read_text(encoding="utf-8")
        committed_schema = yaml.safe_load(content)

        # Parse live schema to plain python types via yaml dump/load for exact structural comparison
        live_yaml_str = yaml.dump(live_schema, sort_keys=True)
        parsed_live_schema = yaml.safe_load(live_yaml_str)

        assert parsed_live_schema == committed_schema, (
            "Committed docs/openapi.yaml has drifted from live DRF Spectacular schema! "
            "Re-generate docs/openapi.yaml using python manage.py spectacular."
        )

    @override_settings(ENABLE_API_DOCS=False)
    def test_docs_ui_disabled_returns_404(self):
        client = Client()
        for endpoint in ("/api/v1/docs/", "/api/v1/redoc/", "/api/v1/schema/"):
            response = client.get(endpoint)
            assert response.status_code == 404, f"Expected 404 for {endpoint} when ENABLE_API_DOCS=False, got {response.status_code}"
            assert response["content-type"] == "application/json"
            assert response.json()["error"]["code"] == "NOT_FOUND"

    @override_settings(ENABLE_API_DOCS=True)
    def test_docs_ui_enabled_serves_endpoints(self):
        client = Client()
        response = client.get("/api/v1/schema/")
        assert response.status_code == 200
        assert "application/vnd.oai.openapi" in response["content-type"] or "yaml" in response["content-type"]
