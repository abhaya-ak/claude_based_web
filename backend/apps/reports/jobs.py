import datetime
import logging

from django.conf import settings
from django.utils import timezone

from apps.core import aws
from apps.core.jobs.registry import register_job
from apps.reports.models import ReportEvidence

logger = logging.getLogger(__name__)

ORPHAN_BATCH_LIMIT = 500
MAX_ORPHAN_DELETES_PER_RUN = ORPHAN_BATCH_LIMIT


@register_job("clean_orphan_evidence")
def clean_orphan_evidence() -> dict:
    """
    Cleans orphan evidence objects in S3 bucket (D82).
    - Only keys under 'evidence/'
    - LastModified older than 24 hours
    - Re-checks DB (ReportEvidence) right before deletion
    - Max 500 keys deleted per run
    - Logs counts only (no keys, no PII)
    - Never touches other prefixes
    """
    s3 = aws.client("s3")
    bucket = settings.EVIDENCE_BUCKET
    now = timezone.now()
    cutoff = now - datetime.timedelta(hours=24)

    scanned_count = 0
    deleted_count = 0

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix="evidence/")
    for page in pages:
        contents = page.get("Contents", [])
        for obj in contents:
            scanned_count += 1
            key = obj.get("Key", "")
            if not key.startswith("evidence/"):
                continue

            last_modified = obj.get("LastModified")
            if not last_modified or last_modified >= cutoff:
                continue

            # Re-check DB right before delete
            if ReportEvidence.objects.filter(s3_key=key).exists():
                continue

            s3.delete_object(Bucket=bucket, Key=key)
            deleted_count += 1

            if deleted_count >= ORPHAN_BATCH_LIMIT:
                break

        if deleted_count >= ORPHAN_BATCH_LIMIT:
            break

    logger.info(
        "Orphan evidence cleanup completed: %d scanned, %d deleted",
        scanned_count,
        deleted_count,
    )
    return {"scanned_count": scanned_count, "deleted_count": deleted_count}
