import hashlib
import struct
from collections.abc import Callable

_JOB_REGISTRY: dict[str, Callable[[], dict]] = {}


def register_job(name: str):
    """Decorator to register a scheduled task in the ScamShield job registry."""
    def decorator(fn: Callable[[], dict]):
        _JOB_REGISTRY[name] = fn
        return fn
    return decorator


def get_job(name: str) -> Callable[[], dict] | None:
    """Retrieves a registered job function by name."""
    return _JOB_REGISTRY.get(name)


def get_all_jobs() -> dict[str, Callable[[], dict]]:
    """Returns a copy of all registered jobs."""
    return dict(_JOB_REGISTRY)


def get_lock_id_for_job(name: str) -> int:
    """
    Computes a deterministic signed 64-bit integer advisory lock key
    for a job name suitable for PostgreSQL pg_try_advisory_lock(bigint).
    """
    digest = hashlib.sha256(f"scamshield-job:{name}".encode()).digest()
    # Signed 64-bit integer (-9223372036854775808 to 9223372036854775807)
    return struct.unpack(">q", digest[:8])[0]
