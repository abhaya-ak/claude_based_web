import pytest


@pytest.fixture(autouse=True)
def _block_aws_network(monkeypatch):
    """Safety fixture: sets dummy AWS credentials and disables IMDS to prevent accidental AWS calls."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-1")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)
    monkeypatch.delenv("AWS_ENDPOINT_URL_SNS", raising=False)
    monkeypatch.delenv("AWS_ENDPOINT_URL_CLOUDWATCH", raising=False)
