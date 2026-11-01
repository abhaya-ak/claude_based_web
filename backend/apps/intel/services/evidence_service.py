import logging

from django.conf import settings

from apps.core import audit
from apps.core.aws import client

logger = logging.getLogger(__name__)


def issue_evidence_presigned_urls(*, report, actor, ip_hash: str = "") -> list[dict]:
    """
    Generates S3 pre-signed get_object download URLs (ExpiresIn=900, attachment)
    for all clean evidence files associated with the report, and audits the event.
    """
    s3 = client("s3")
    bucket = getattr(settings, "EVIDENCE_BUCKET", "scamshield-evidence-dev")
    results = []

    for ev in report.evidence.all():
        safe_name = ev.s3_key.split("/")[-1]
        try:
            url = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": bucket,
                    "Key": ev.s3_key,
                    "ResponseContentDisposition": f'attachment; filename="{safe_name}"',
                },
                ExpiresIn=900,
            )
        except Exception:
            logger.exception("Failed to generate presigned URL for evidence %s", ev.id)
            continue

        results.append(
            {
                "id": str(ev.id),
                "mime_type": ev.content_type,
                "content_type": ev.content_type,
                "size_bytes": ev.size_bytes,
                "download_url": url,
                "expires_in": 900,
            }
        )

    # Audit event per request
    audit.log_event(
        "EVIDENCE_URL_ISSUED",
        actor=actor,
        target=report,
        ip_hash=ip_hash,
        metadata={"file_count": len(results)},
    )

    return results
