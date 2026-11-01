from django.db import transaction
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import User
from apps.core.audit import log_event
from apps.ops.models import AuditEventType


def change_user_password(user: User, new_password: str, ip_hash: str) -> None:
    """
    D48: Changes user's password, invalidates ALL outstanding refresh tokens
    across all sessions, and writes PASSWORD_CHANGED audit log.
    """
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Blacklist all outstanding tokens for this user
        outstanding = OutstandingToken.objects.filter(user=user)
        for ot in outstanding:
            BlacklistedToken.objects.get_or_create(token=ot)

    log_event(
        event_type=AuditEventType.PASSWORD_CHANGED,
        actor=user,
        ip_hash=ip_hash,
        target=("USER", str(user.id)),
    )
