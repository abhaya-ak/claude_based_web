from rest_framework.permissions import BasePermission

from apps.accounts.models import ApprovalStatus, Role


class IsEducatorOrAdmin(BasePermission):
    """Allows access only to approved EDUCATOR or ADMIN users per D112."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "approval_status", None) == ApprovalStatus.APPROVED
            and getattr(user, "role", None) in {Role.EDUCATOR, Role.ADMIN}
        )


class IsGuideAuthorOrAdmin(BasePermission):
    """Object-level permission allowing ADMIN or the original author EDUCATOR per D112."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "approval_status", None) == ApprovalStatus.APPROVED
            and getattr(user, "role", None) in {Role.EDUCATOR, Role.ADMIN}
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if getattr(user, "role", None) == Role.ADMIN:
            return True

        if getattr(user, "role", None) == Role.EDUCATOR:
            return getattr(obj, "author_id", None) == user.id

        return False
