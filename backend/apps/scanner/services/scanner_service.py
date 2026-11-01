import logging
import uuid

logger = logging.getLogger(__name__)


def dispatch_scan(report_id: uuid.UUID) -> None:
    """
    Phase 4 stub: gathers report narrative, indicators, active rules, and config.
    Invokes Lambda scanner asynchronously via transaction.on_commit() (Phase 5).
    In Phase 4, logs INFO and returns None. Wrapped failure-tolerant per R-A6.
    """
    try:
        logger.info("Scanner dispatch_scan stub called for report %s", report_id)
    except Exception as exc:
        logger.warning("Scanner dispatch_scan stub warning: %s", exc)
