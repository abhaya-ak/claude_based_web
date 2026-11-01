import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.audit import log_event
from apps.core.errors import ConflictError
from apps.ops.models import AuditEventType


def approve_staff_user(admin_user: User, target_id: uuid.UUID, ip_hash: str) -> User:
    """
    D50: Approves a PENDING staff account.
    Target user must have a staff role and approval_status == PENDING.
    """
    with transaction.atomic():
        target_user = User.objects.select_for_update().filter(id=target_id).first()
        if not target_user:
            raise NotFound("User not found.")

        if (
            target_user.role not in [Role.ANALYST, Role.EDUCATOR, Role.ADMIN]
            or target_user.approval_status != ApprovalStatus.PENDING
        ):
            raise ConflictError("User is not a pending staff account.")

        target_user.approval_status = ApprovalStatus.APPROVED
        target_user.approved_by = admin_user
        target_user.approved_at = timezone.now()
        target_user.rejection_reason = ""
        target_user.save(update_fields=["approval_status", "approved_by", "approved_at", "rejection_reason", "updated_at"])

    log_event(
        event_type=AuditEventType.ROLE_APPROVED,
        actor=admin_user,
        ip_hash=ip_hash,
        target=("USER", str(target_user.id)),
        metadata={"approved_role": target_user.role},
    )
    return target_user


def reject_staff_user(admin_user: User, target_id: uuid.UUID, reason: str, ip_hash: str) -> User:
    """
    D50: Rejects a PENDING staff account with required reason.
    Blacklists any outstanding refresh tokens as defense-in-depth.
    """
    with transaction.atomic():
        target_user = User.objects.select_for_update().filter(id=target_id).first()
        if not target_user:
            raise NotFound("User not found.")

        if target_user.approval_status != ApprovalStatus.PENDING:
            raise ConflictError("User is not in pending status.")

        target_user.approval_status = ApprovalStatus.REJECTED
        target_user.rejection_reason = reason
        target_user.approved_by = None
        target_user.approved_at = None
        target_user.save(update_fields=["approval_status", "rejection_reason", "approved_by", "approved_at", "updated_at"])

        # Blacklist any outstanding tokens for this user
        outstanding = OutstandingToken.objects.filter(user=target_user)
        for ot in outstanding:
            BlacklistedToken.objects.get_or_create(token=ot)

    log_event(
        event_type=AuditEventType.ROLE_REJECTED,
        actor=admin_user,
        ip_hash=ip_hash,
        target=("USER", str(target_user.id)),
        metadata={"requested_role": target_user.role},
    )
    return target_user


def change_user_role(admin_user: User, target_id: uuid.UUID, new_role: str, ip_hash: str) -> User:
    """
    D50: Changes user's role.
    Guards:
    - Admin cannot change own role.
    - Last active approved ADMIN cannot be demoted.
    - Blacklists outstanding tokens.
    """
    if str(admin_user.id) == str(target_id):
        raise ConflictError("Administrators cannot change their own role.")

    with transaction.atomic():
        target_user = User.objects.select_for_update().filter(id=target_id).first()
        if not target_user:
            raise NotFound("User not found.")

        # Last active admin guard
        if (
            target_user.role == Role.ADMIN
            and target_user.is_active
            and target_user.approval_status == ApprovalStatus.APPROVED
            and new_role != Role.ADMIN
        ):
            active_admin_count = (
                User.objects.select_for_update()
                .filter(role=Role.ADMIN, is_active=True, approval_status=ApprovalStatus.APPROVED)
                .count()
            )
            if active_admin_count <= 1:
                raise ConflictError("Cannot demote the last active administrator.")

        old_role = target_user.role
        target_user.role = new_role

        # If promoting to a staff role, ensure approved
        update_fields = ["role", "updated_at"]
        if new_role != Role.CITIZEN and target_user.approval_status != ApprovalStatus.APPROVED:
            target_user.approval_status = ApprovalStatus.APPROVED
            target_user.approved_by = admin_user
            target_user.approved_at = timezone.now()
            update_fields.extend(["approval_status", "approved_by", "approved_at"])

        target_user.save(update_fields=update_fields)

        # Invalidate existing sessions so permissions update immediately
        outstanding = OutstandingToken.objects.filter(user=target_user)
        for ot in outstanding:
            BlacklistedToken.objects.get_or_create(token=ot)

    log_event(
        event_type=AuditEventType.ROLE_CHANGED,
        actor=admin_user,
        ip_hash=ip_hash,
        target=("USER", str(target_user.id)),
        metadata={"old_role": old_role, "new_role": new_role},
    )
    return target_user
