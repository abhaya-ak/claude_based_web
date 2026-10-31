import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel


class Role(models.TextChoices):
    CITIZEN = "CITIZEN", "Citizen"
    ANALYST = "ANALYST", "Analyst"
    EDUCATOR = "EDUCATOR", "Educator"
    ADMIN = "ADMIN", "Admin"


class ApprovalStatus(models.TextChoices):
    APPROVED = "APPROVED", "Approved"
    PENDING = "PENDING", "Pending"
    REJECTED = "REJECTED", "Rejected"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", Role.CITIZEN)
        if extra_fields.get("role") == Role.CITIZEN:
            extra_fields.setdefault("approval_status", ApprovalStatus.APPROVED)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        extra_fields.setdefault("approval_status", ApprovalStatus.APPROVED)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CITIZEN)
    approval_status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.APPROVED
    )
    organization = models.CharField(max_length=200, null=True, blank=True)
    credential_note = models.TextField(max_length=1000, null=True, blank=True)
    approved_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_users",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=300, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "accounts_user"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="uq_user_email_lower",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values),
                name="ck_user_role",
            ),
            models.CheckConstraint(
                condition=models.Q(approval_status__in=ApprovalStatus.values),
                name="ck_user_approval_status",
            ),
            models.CheckConstraint(
                condition=~models.Q(role=Role.CITIZEN) | models.Q(approval_status=ApprovalStatus.APPROVED),
                name="ck_user_citizen_approved",
            ),
        ]

    def __str__(self):
        return f"User({self.id}, role={self.role})"

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    @property
    def is_staff(self):
        return self.role in (Role.ADMIN, Role.ANALYST, Role.EDUCATOR)
