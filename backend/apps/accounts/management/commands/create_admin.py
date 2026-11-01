import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.audit import log_event
from apps.ops.models import AuditEventType


class Command(BaseCommand):
    help = "Idempotently creates or updates an active approved Administrator (D51)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Administrator email address")
        parser.add_argument("--full-name", default="System Administrator", help="Administrator full name")
        parser.add_argument("--no-input", action="store_true", help="Do not prompt for password interactively")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        full_name = options.get("full_name") or "System Administrator"
        no_input = options.get("no_input", False)

        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            if no_input:
                raise CommandError("ADMIN_PASSWORD environment variable is required when using --no-input.")
            password = getpass.getpass("Enter administrator password: ")

        try:
            validate_password(password)
        except ValidationError as e:
            raise CommandError(f"Password does not meet security requirements: {'; '.join(e.messages)}") from e

        user = User.objects.filter(email=email).first()
        if user:
            old_role = user.role
            user.role = Role.ADMIN
            user.approval_status = ApprovalStatus.APPROVED
            user.is_active = True
            user.full_name = full_name
            user.set_password(password)
            user.save()

            if old_role != Role.ADMIN:
                log_event(
                    event_type=AuditEventType.ROLE_CHANGED,
                    actor=user,
                    target=("USER", str(user.id)),
                    metadata={"old_role": old_role, "new_role": Role.ADMIN},
                )
            self.stdout.write(self.style.SUCCESS(f"User {email} updated to active approved Administrator."))
        else:
            user = User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                role=Role.ADMIN,
                approval_status=ApprovalStatus.APPROVED,
            )
            log_event(
                event_type=AuditEventType.USER_REGISTERED,
                actor=user,
                target=("USER", str(user.id)),
                metadata={"role": Role.ADMIN},
            )
            self.stdout.write(self.style.SUCCESS(f"Administrator {email} created successfully."))
