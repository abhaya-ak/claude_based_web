from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ApprovalStatus, Role, User
from apps.accounts.throttling import check_login_failure_throttle, check_registration_throttle
from apps.core.audit import log_event
from apps.core.errors import AccountNotApproved, ConflictError
from apps.ops.models import AuditEventType, AuditSeverity

# Pre-computed Argon2 hash to ensure identical timing on unknown email lookup
DUMMY_PASSWORD_HASH = make_password("scamshield-dummy-password-for-timing-equalization")


def register_citizen(data: dict, ip_hash: str) -> User:
    """
    D46: Registers a CITIZEN user.
    Ignores any role field in data. Enforces unique email (case-insensitive).
    Audits USER_REGISTERED. Issues no tokens.
    """
    check_registration_throttle(ip_hash)

    email = data["email"].strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise ConflictError("An account with this email already exists.")

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=data["password"],
                full_name=data["full_name"],
                role=Role.CITIZEN,
                approval_status=ApprovalStatus.APPROVED,
            )
    except IntegrityError as e:
        raise ConflictError("An account with this email already exists.") from e

    log_event(
        event_type=AuditEventType.USER_REGISTERED,
        actor=user,
        ip_hash=ip_hash,
        target=("USER", str(user.id)),
    )
    return user


def register_staff(data: dict, ip_hash: str) -> User:
    """
    D46: Registers an ANALYST or EDUCATOR user in PENDING status.
    Requires organization and credential_note. Enforces unique email.
    Audits STAFF_REGISTERED. Issues no tokens.
    """
    check_registration_throttle(ip_hash)

    email = data["email"].strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise ConflictError("An account with this email already exists.")

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=data["password"],
                full_name=data["full_name"],
                role=data["role"],
                approval_status=ApprovalStatus.PENDING,
                organization=data["organization"],
                credential_note=data["credential_note"],
            )
    except IntegrityError as e:
        raise ConflictError("An account with this email already exists.") from e

    log_event(
        event_type=AuditEventType.STAFF_REGISTERED,
        actor=user,
        ip_hash=ip_hash,
        target=("USER", str(user.id)),
        metadata={"requested_role": user.role},
    )
    return user


def login_user(email: str, raw_password: str, ip_hash: str) -> tuple[User, str, str]:
    """
    D45: Timing-safe login with audit throttling.
    Returns (user, access_token, refresh_token).
    """
    norm_email = email.strip().lower()
    user = User.objects.filter(email__iexact=norm_email).first()

    # Check failure throttle before checking credentials
    check_login_failure_throttle(ip_hash=ip_hash, target_user=user)

    if user is None:
        # Run dummy Argon2 check to normalize timing
        check_password(raw_password, DUMMY_PASSWORD_HASH)
        log_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            ip_hash=ip_hash,
            severity=AuditSeverity.WARN,
        )
        raise exceptions.AuthenticationFailed(
            detail="Invalid email or password.",
            code="authentication_failed",
        )

    if not user.check_password(raw_password) or not user.is_active:
        log_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            actor=user,
            ip_hash=ip_hash,
            target=("USER", str(user.id)),
            severity=AuditSeverity.WARN,
        )
        raise exceptions.AuthenticationFailed(
            detail="Invalid email or password.",
            code="authentication_failed",
        )

    # Check staff approval status
    if user.role != Role.CITIZEN and user.approval_status != ApprovalStatus.APPROVED:
        raise AccountNotApproved()

    # Successful login
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    log_event(
        event_type=AuditEventType.LOGIN_SUCCESS,
        actor=user,
        ip_hash=ip_hash,
        target=("USER", str(user.id)),
    )

    return user, access_token, refresh_token


def refresh_token(raw_refresh_token: str) -> tuple[str, str]:
    """
    D44, D49: Validates refresh token from cookie, rotates token,
    blacklists previous token, and returns (new_access, new_refresh).
    """
    if not raw_refresh_token:
        raise exceptions.AuthenticationFailed(
            detail="Refresh token cookie missing.",
            code="authentication_failed",
        )

    try:
        old_token = RefreshToken(raw_refresh_token)
        user_id = old_token["user_id"]
    except Exception as e:
        raise exceptions.AuthenticationFailed(
            detail="Invalid or expired refresh token.",
            code="authentication_failed",
        ) from e

    user = User.objects.filter(id=user_id).first()
    if not user or not user.is_active:
        raise exceptions.AuthenticationFailed(
            detail="User account is deactivated or invalid.",
            code="authentication_failed",
        )

    if user.role != Role.CITIZEN and user.approval_status != ApprovalStatus.APPROVED:
        try:
            old_token.blacklist()
        except Exception:
            pass
        raise AccountNotApproved()

    # Blacklist old token and rotate
    try:
        old_token.blacklist()
    except Exception as e:
        raise exceptions.AuthenticationFailed(
            detail="Token has already been used or blacklisted.",
            code="authentication_failed",
        ) from e

    new_refresh = RefreshToken.for_user(user)
    return str(new_refresh.access_token), str(new_refresh)


def logout_user(raw_refresh_token: str | None) -> None:
    """
    D44: Blacklists the refresh token if valid; never raises on invalid/missing token.
    """
    if not raw_refresh_token:
        return
    try:
        token = RefreshToken(raw_refresh_token)
        token.blacklist()
    except Exception:
        pass
