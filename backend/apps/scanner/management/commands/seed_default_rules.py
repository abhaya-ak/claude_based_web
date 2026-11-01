from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import ApprovalStatus, Role, User
from apps.scanner.models import HeuristicRule, RuleType, ScannerConfig

DEFAULT_KEYWORDS = [
    ("urgent", 15),
    ("verify", 15),
    ("suspend", 15),
    ("otp", 15),
    ("bank", 15),
    ("police", 15),
    ("court", 15),
    ("arrest", 15),
    ("lhdn", 15),
    ("cimb", 15),
    ("maybank", 15),
    ("touchngo", 15),
]

DEFAULT_TLDS = [
    (".xyz", 25),
    (".top", 25),
    (".vip", 25),
    (".icu", 25),
    (".buzz", 25),
    (".club", 25),
    (".work", 25),
    (".cn", 25),
]

DEFAULT_SHORTENERS = [
    ("bit.ly", 15),
    ("tinyurl.com", 15),
    ("t.co", 15),
    ("cutt.ly", 15),
    ("is.gd", 15),
    ("rb.gy", 15),
]


class Command(BaseCommand):
    help = "Idempotently seeds baseline heuristic rules (FR-4.1.3) and ensures ScannerConfig(id=1) exists (D93)."

    def handle(self, *args, **options):
        admin_user = (
            User.objects.filter(role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED).first()
            or User.objects.filter(role=Role.ADMIN).first()
        )
        if not admin_user:
            self.stdout.write(
                self.style.WARNING("No ADMIN user found. Default rules will not be created without an admin user.")
            )
            return

        with transaction.atomic():
            ScannerConfig.objects.get_or_create(
                id=1,
                defaults={
                    "keyword_cap_points": 45,
                    "ip_url_points": 25,
                    "prior_pending_points": 20,
                    "high_priority_threshold": 75,
                    "ruleset_version": 1,
                    "updated_by": admin_user,
                },
            )

            created_count = 0
            for pattern, weight in DEFAULT_KEYWORDS:
                _, created = HeuristicRule.objects.get_or_create(
                    rule_type=RuleType.KEYWORD,
                    pattern=pattern.lower().strip(),
                    defaults={"weight": weight, "is_active": True, "created_by": admin_user},
                )
                if created:
                    created_count += 1

            for pattern, weight in DEFAULT_TLDS:
                _, created = HeuristicRule.objects.get_or_create(
                    rule_type=RuleType.TLD,
                    pattern=pattern.lower().strip(),
                    defaults={"weight": weight, "is_active": True, "created_by": admin_user},
                )
                if created:
                    created_count += 1

            for pattern, weight in DEFAULT_SHORTENERS:
                _, created = HeuristicRule.objects.get_or_create(
                    rule_type=RuleType.SHORTENER,
                    pattern=pattern.lower().strip(),
                    defaults={"weight": weight, "is_active": True, "created_by": admin_user},
                )
                if created:
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed completed: {created_count} rules created. Total rules: {HeuristicRule.objects.count()}."
            )
        )
