import logging
import re
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    return correlation_id_var.get()


def set_correlation_id(value: str) -> None:
    correlation_id_var.set(value)


FORBIDDEN_PII_KEYS = {
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "phone",
    "email",
    "bank_account",
    "id_number",
    "victim_name",
    "reporter_name",
    "evidence",
    "national_id",
    "credit_card",
    "pin",
    "cvv",
}


def _scrub_data(data):
    if isinstance(data, dict):
        scrubbed = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(forbidden in k_lower for forbidden in FORBIDDEN_PII_KEYS):
                scrubbed[k] = "[REDACTED]"
            else:
                scrubbed[k] = _scrub_data(v)
        return scrubbed
    elif isinstance(data, list):
        return [_scrub_data(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(_scrub_data(item) for item in data)
    return data


class PiiScrubberFilter(logging.Filter):
    """Filter that inspects and sanitizes forbidden PII keys in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Strip raw request objects so they are never serialized with query strings or headers
        if hasattr(record, "request"):
            delattr(record, "request")

        # Scrub attributes on record
        for key, value in list(record.__dict__.items()):
            if key in ("name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process"):
                continue
            setattr(record, key, _scrub_data(value))

        # Scrub args if passed as dict or list
        if isinstance(record.args, dict):
            record.args = _scrub_data(record.args)
        elif isinstance(record.args, (list, tuple)):
            record.args = tuple(_scrub_data(arg) for arg in record.args)

        # Scrub message text if string
        if isinstance(record.msg, str):
            for forbidden in FORBIDDEN_PII_KEYS:
                # Mask patterns like password=..., token: ...
                record.msg = re.sub(
                    rf"(?i)\b({forbidden})\b\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?",
                    r"\1=[REDACTED]",
                    record.msg,
                )

        return True
