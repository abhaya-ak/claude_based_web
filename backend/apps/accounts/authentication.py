from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.models import ApprovalStatus, Role
from apps.core.errors import AccountNotApproved


class ScamShieldJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT to enforce ScamShield DB-backed authorization:
    - User must exist and be active.
    - Staff roles (ANALYST, EDUCATOR, ADMIN) must have approval_status == APPROVED.
    - If staff account is PENDING or REJECTED, raises 403 account_not_approved (D45, D49).
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        if not user.is_active:
            raise exceptions.AuthenticationFailed(
                detail="User account is deactivated.",
                code="authentication_failed",
            )

        if user.role != Role.CITIZEN and user.approval_status != ApprovalStatus.APPROVED:
            raise AccountNotApproved()

        return user
