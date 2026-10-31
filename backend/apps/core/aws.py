import threading

import boto3
from botocore.config import Config
from django.conf import settings

_client_lock = threading.Lock()
_client_cache: dict[str, boto3.client] = {}


def client(service_name: str) -> boto3.client:
    """Returns a thread-safe cached boto3 client configured with timeouts and retries per R-A6 / D31."""
    with _client_lock:
        if service_name in _client_cache:
            return _client_cache[service_name]

        region = getattr(settings, "AWS_REGION", None) or getattr(settings, "AWS_DEFAULT_REGION", "ap-southeast-1")
        endpoint_url = getattr(settings, "AWS_ENDPOINT_URL", None)

        boto_config = Config(
            connect_timeout=2,
            read_timeout=5,
            retries={"max_attempts": 2},
        )

        kwargs = {
            "service_name": service_name,
            "region_name": region,
            "config": boto_config,
        }
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url

        cli = boto3.client(**kwargs)
        _client_cache[service_name] = cli
        return cli


def reset_clients() -> None:
    """Clears the client cache (used in tests)."""
    with _client_lock:
        _client_cache.clear()
