from rest_framework.permissions import BasePermission

from apps.accounts.models import ApprovalStatus, Role


class HasRole(BasePermission):
    """Allows access only to users with specific roles."""

    def __init__(self, *allowed_roles):
        self.allowed_roles = set(allowed_roles)

    def __call__(self):
        # Enables use as permission class or instance
        return self

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.role in self.allowed_roles


class IsApprovedStaff(BasePermission):
    """Allows access only to approved staff (ANALYST, EDUCATOR, ADMIN)."""

    ALLOWED_STAFF_ROLES = {Role.ANALYST, Role.EDUCATOR, Role.ADMIN}

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (
            request.user.role in self.ALLOWED_STAFF_ROLES
            and request.user.approval_status == ApprovalStatus.APPROVED
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: allows access if user is approved ADMIN or
    owns the object (matching obj.user, obj.reporter, obj.author, or obj == request.user).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False

        if (
            request.user.role == Role.ADMIN
            and request.user.approval_status == ApprovalStatus.APPROVED
        ):
            return True

        # Check direct identity
        if obj == request.user:
            return True

        # Check various ownership attributes
        owner = getattr(obj, "user", None) or getattr(obj, "reporter", None) or getattr(obj, "author", None)
        return owner == request.user
