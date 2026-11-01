import pytest
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.authentication import ScamShieldJWTAuthentication
from apps.accounts.cookies import clear_refresh_cookie, require_csrf_header, set_refresh_cookie
from apps.accounts.models import ApprovalStatus, Role
from apps.accounts.permissions import HasRole, IsApprovedStaff, IsOwnerOrAdmin
from apps.accounts.tests.factories import UserFactory
from apps.accounts.throttling import check_login_failure_throttle, check_registration_throttle
from apps.core.errors import AccountNotApproved
from apps.ops.models import AuditEventType, SystemAuditLog


@pytest.mark.django_db
class TestSimpleJWTUUIDCompatibility:
    """TO BE PROVEN #1: Prove UUID user id works in SimpleJWT tokens."""

    def test_uuid_user_id_in_tokens(self):
        user = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        refresh = RefreshToken.for_user(user)
        access_token_str = str(refresh.access_token)

        # Verify access token claim contains user id as string of uuid
        validated_token = AccessToken(access_token_str)
        assert validated_token["user_id"] == str(user.id)

        # Authenticate via ScamShieldJWTAuthentication
        factory = APIRequestFactory()
        request = factory.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access_token_str}")
        authenticator = ScamShieldJWTAuthentication()
        auth_user, token = authenticator.authenticate(request)
        assert auth_user.id == user.id

    def test_unapproved_staff_rejected_by_authentication(self):
        user = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.PENDING)
        refresh = RefreshToken.for_user(user)
        access_token_str = str(refresh.access_token)

        factory = APIRequestFactory()
        request = factory.get("/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access_token_str}")
        authenticator = ScamShieldJWTAuthentication()
        with pytest.raises(AccountNotApproved):
            authenticator.authenticate(request)


@pytest.mark.django_db
class TestCookieAndHeaderHelpers:
    def test_set_refresh_cookie_attributes(self):
        response = HttpResponse()
        set_refresh_cookie(response, "sample_refresh_token")
        cookie = response.cookies.get(settings.REFRESH_COOKIE_NAME)
        assert cookie is not None
        assert cookie.value == "sample_refresh_token"
        assert cookie["httponly"] is True
        assert cookie["samesite"].lower() == "lax"
        assert cookie["path"] == "/api/v1/auth/"
        assert int(cookie["max-age"]) == 7 * 24 * 3600

    def test_clear_refresh_cookie_attributes(self):
        response = HttpResponse()
        set_refresh_cookie(response, "sample_refresh_token")
        clear_refresh_cookie(response)
        cookie = response.cookies.get(settings.REFRESH_COOKIE_NAME)
        assert cookie.value == ""
        assert int(cookie["max-age"]) == 0
        assert cookie["path"] == "/api/v1/auth/"

    def test_require_csrf_header_success(self):
        request = HttpRequest()
        request.headers = {"X-Requested-With": "scamshield-web"}
        # Should not raise
        require_csrf_header(request)

    def test_require_csrf_header_missing_or_wrong(self):
        request = HttpRequest()
        request.headers = {}
        with pytest.raises(exceptions.PermissionDenied) as exc:
            require_csrf_header(request)
        assert exc.value.detail.code == "permission_denied"

        request.headers = {"X-Requested-With": "wrong-client"}
        with pytest.raises(exceptions.PermissionDenied) as exc:
            require_csrf_header(request)
        assert exc.value.detail.code == "permission_denied"


@pytest.mark.django_db
class TestAuditThrottlingHelpers:
    def test_login_failure_throttle_by_ip(self):
        ip_hash = "a" * 64
        # 9 failures exist in DB -> 10th attempt is allowed
        for _ in range(9):
            SystemAuditLog.objects.create(
                event_type=AuditEventType.LOGIN_FAILURE,
                actor_ip_hash=ip_hash,
                severity="WARN",
                metadata={},
            )
        # 10th attempt check passes
        check_login_failure_throttle(ip_hash=ip_hash, target_user=None)

        # 10th failure occurs and is logged
        SystemAuditLog.objects.create(
            event_type=AuditEventType.LOGIN_FAILURE,
            actor_ip_hash=ip_hash,
            severity="WARN",
            metadata={},
        )
        # 11th attempt is blocked
        with pytest.raises(exceptions.Throttled) as exc:
            check_login_failure_throttle(ip_hash=ip_hash, target_user=None)
        assert exc.value.wait == 900

        # Verify RATE_LIMIT_BLOCK row was written
        assert SystemAuditLog.objects.filter(
            event_type=AuditEventType.RATE_LIMIT_BLOCK,
            actor_ip_hash=ip_hash,
        ).exists()

        # Other IP is unaffected
        other_ip = "b" * 64
        check_login_failure_throttle(ip_hash=other_ip, target_user=None)

    def test_login_failure_throttle_by_target_account(self):
        user = UserFactory()
        ip_1 = "1" * 64
        ip_2 = "2" * 64
        # 10 failures logged for account
        for _ in range(10):
            SystemAuditLog.objects.create(
                event_type=AuditEventType.LOGIN_FAILURE,
                actor_ip_hash=ip_1,
                target_type="USER",
                target_id=str(user.id),
                severity="WARN",
                metadata={},
            )
        # 11th attempt from different IP for the same target user should be blocked
        with pytest.raises(exceptions.Throttled) as exc:
            check_login_failure_throttle(ip_hash=ip_2, target_user=user)
        assert exc.value.wait == 900

    def test_registration_throttle_by_ip(self):
        ip_hash = "c" * 64
        # 9 registrations exist -> 10th attempt is allowed
        for _ in range(9):
            SystemAuditLog.objects.create(
                event_type=AuditEventType.USER_REGISTERED,
                actor_ip_hash=ip_hash,
                severity="INFO",
                metadata={},
            )
        check_registration_throttle(ip_hash=ip_hash)

        # 10th registration logged
        SystemAuditLog.objects.create(
            event_type=AuditEventType.STAFF_REGISTERED,
            actor_ip_hash=ip_hash,
            severity="INFO",
            metadata={},
        )
        # 11th registration is blocked
        with pytest.raises(exceptions.Throttled) as exc:
            check_registration_throttle(ip_hash=ip_hash)
        assert exc.value.wait == 3600


@pytest.mark.django_db
class TestRBACPermissions:
    def test_has_role_permission(self):
        perm = HasRole(Role.ADMIN)
        request = HttpRequest()
        request.user = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        assert perm.has_permission(request, None) is False

        request.user = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)
        assert perm.has_permission(request, None) is True

    def test_is_approved_staff_permission(self):
        perm = IsApprovedStaff()
        request = HttpRequest()
        # Pending analyst fails
        request.user = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.PENDING)
        assert perm.has_permission(request, None) is False

        # Approved analyst passes
        request.user = UserFactory(role=Role.ANALYST, approval_status=ApprovalStatus.APPROVED)
        assert perm.has_permission(request, None) is True

        # Citizen fails even if approved
        request.user = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        assert perm.has_permission(request, None) is False

    def test_is_owner_or_admin_permission(self):
        perm = IsOwnerOrAdmin()
        request = HttpRequest()
        owner = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        other = UserFactory(role=Role.CITIZEN, approval_status=ApprovalStatus.APPROVED)
        admin = UserFactory(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED)

        class DummyObj:
            def __init__(self, user):
                self.reporter = user

        obj = DummyObj(owner)

        request.user = other
        assert perm.has_object_permission(request, None, obj) is False

        request.user = owner
        assert perm.has_object_permission(request, None, obj) is True

        request.user = admin
        assert perm.has_object_permission(request, None, obj) is True
