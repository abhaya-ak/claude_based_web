from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.core.jobs.registry import register_job


@register_job("flush_expired_tokens")
def flush_expired_tokens() -> dict:
    """
    Deletes expired OutstandingToken rows (and cascades to BlacklistedToken)
    where expires_at <= timezone.now() (D51).
    """
    now = timezone.now()
    deleted_count, _ = OutstandingToken.objects.filter(expires_at__lte=now).delete()
    return {"deleted_tokens": deleted_count}
