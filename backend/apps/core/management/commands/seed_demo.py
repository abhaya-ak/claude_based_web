import os
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import ApprovalStatus, Role, User
from apps.broadcasts.models import AdvisorySeverity, AdvisoryStatus, ThreatAdvisory
from apps.core.enums import AudienceGroup
from apps.intel.models import IndicatorStatus, IndicatorType, ThreatLevel, VerifiedIndicator
from apps.literacy.models import (
    AttemptAnswer,
    AttemptStatus,
    ScenarioStatus,
    SimulatorAttempt,
    SimulatorScenario,
)
from apps.ops.models import AuditEventType, AuditSeverity, SystemAuditLog
from apps.reports.models import (
    Platform,
    ReportIndicator,
    ReportStatus,
    ScamCategory,
    ScamReport,
)
from apps.reports.normalizers import (
    normalize_bank_account,
    normalize_phone,
)


class Command(BaseCommand):
    help = "Idempotently seeds demo data for local demonstration and load testing per D136."

    def add_arguments(self, parser):
        parser.add_argument(
            "--i-know-what-i-am-doing",
            action="store_true",
            default=False,
            help="Mandatory safety confirmation flag to allow seeding.",
        )
        parser.add_argument(
            "--scale",
            choices=["small", "load"],
            default="small",
            help="Data scale: 'small' (default demo) or 'load' (20k reports, 20k indicators, 50k audit logs).",
        )

    def handle(self, *args, **options):
        # 1. Safety verification
        if not options.get("i_know_what_i_am_doing"):
            raise CommandError("Refusing to seed demo data without --i-know-what-i-am-doing flag.")

        if not getattr(settings, "DEBUG", False):
            raise CommandError("Refusing to seed demo data when DEBUG is False.")

        db_host = settings.DATABASES.get("default", {}).get("HOST", "")
        allowed_hosts = {"localhost", "127.0.0.1", "db", "postgres", ""}
        if db_host not in allowed_hosts and not db_host.startswith("127."):
            raise CommandError(f"Refusing to seed demo data on non-local database host '{db_host}'.")

        password = os.environ.get("SEED_DEMO_PASSWORD") or os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError("Environment variable SEED_DEMO_PASSWORD (or DEMO_PASSWORD) must be set.")

        scale = options.get("scale", "small")
        self.stdout.write(f"Starting seed_demo (scale: {scale})...")

        with transaction.atomic():
            # 2. Seed Base Roles
            users = self._seed_users(password)

            # 3. Invoke Sub-Seeders
            self._invoke_sub_commands()

            # 4. Seed Verified Indicators & Threat Intel
            analyst = users["analyst"]
            vis = self._seed_verified_indicators(analyst)

            # 5. Seed Reports & Indicators
            self._seed_reports_and_indicators(users["citizen"], vis)

            # 6. Seed Threat Advisories
            self._seed_advisories(analyst)

            # 7. Seed Simulator Attempts
            self._seed_simulator_attempts(users["citizen"], users["educator"])

            # 8. Seed Audit Logs
            self._seed_audit_logs(users["admin"])

            # 9. Load Scale generation if requested
            if scale == "load":
                self._seed_load_scale_data()

        # Run ANALYZE after transaction commit
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE;")

        self.stdout.write(self.style.SUCCESS(f"seed_demo completed successfully for scale '{scale}'."))

    def _seed_users(self, password: str) -> dict[str, User]:
        roles_data = [
            ("admin@scamshield.gov", Role.ADMIN, "System Administrator"),
            ("analyst@scamshield.gov", Role.ANALYST, "Senior Threat Analyst"),
            ("educator@scamshield.gov", Role.EDUCATOR, "Digital Literacy Specialist"),
            ("citizen@example.com", Role.CITIZEN, "Concerned Citizen"),
        ]
        seeded_users = {}
        for email, role, full_name in roles_data:
            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    role=role,
                    approval_status=ApprovalStatus.APPROVED,
                    full_name=full_name,
                )
            else:
                user.set_password(password)
                user.role = role
                user.approval_status = ApprovalStatus.APPROVED
                user.full_name = full_name
                user.save()
            seeded_users[role.lower()] = user
        return seeded_users

    def _invoke_sub_commands(self):
        try:
            call_command("seed_playbooks")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"seed_playbooks note: {e}"))
        try:
            call_command("seed_default_rules")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"seed_default_rules note: {e}"))
        try:
            call_command("seed_guides")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"seed_guides note: {e}"))
        try:
            call_command("seed_scenarios")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"seed_scenarios note: {e}"))

    def _seed_verified_indicators(self, analyst: User) -> list[VerifiedIndicator]:
        items = [
            (IndicatorType.PHONE, "+60123456789", "+60123456789", ScamCategory.IMPERSONATION.value, ThreatLevel.HIGH, "Known impersonation scam line"),
            (IndicatorType.PHONE, "+60198765432", "+60198765432", ScamCategory.FAKE_JOB.value, ThreatLevel.CRITICAL, "Active fake investment recruiter"),
            (IndicatorType.DOMAIN, "phish-bank-secure.com", "phish-bank-secure.com", ScamCategory.PHISHING.value, ThreatLevel.HIGH, "Credential harvesting portal"),
            (IndicatorType.URL, "https://phish-bank-secure.com/login", "phish-bank-secure.com/login", ScamCategory.PHISHING.value, ThreatLevel.HIGH, "Target login landing page"),
            (IndicatorType.EMAIL, "support@phish-bank-secure.com", "support@phish-bank-secure.com", ScamCategory.PHISHING.value, ThreatLevel.MEDIUM, "Spoofed sender address"),
        ]

        # Add BANK_ACCOUNT with proper HMAC
        acct_norm, acct_disp = normalize_bank_account("123456789012")
        items.append((IndicatorType.BANK_ACCOUNT, acct_norm, acct_disp, ScamCategory.FAKE_JOB.value, ThreatLevel.CRITICAL, "Mule account used in investment scam"))

        created_vis = []
        now = timezone.now()
        for itype, norm_val, disp_val, pcat, tlevel, note in items:
            vi, _ = VerifiedIndicator.objects.update_or_create(
                type=itype,
                normalized_value=norm_val,
                defaults={
                    "display_value": disp_val,
                    "primary_category": pcat,
                    "status": IndicatorStatus.ACTIVE,
                    "threat_level": tlevel,
                    "verified_by": analyst,
                    "verified_at": now - timezone.timedelta(days=20),
                    "public_note": note,
                    "total_report_count": 5,
                    "first_seen_at": now - timezone.timedelta(days=30),
                    "last_seen_at": now,
                },
            )
            created_vis.append(vi)
        return created_vis

    def _seed_reports_and_indicators(self, citizen: User, vis: list[VerifiedIndicator]):
        if ScamReport.objects.filter(reference_code__startswith="SCM-DEMO-").exists():
            return

        demo_reports = [
            ("SCM-DEMO-PHISH01", ScamCategory.PHISHING, Platform.EMAIL, ReportStatus.VERIFIED, 90, True, 0),
            ("SCM-DEMO-INVEST1", ScamCategory.FAKE_JOB, Platform.WHATSAPP, ReportStatus.VERIFIED, 85, True, 1),
            ("SCM-DEMO-PENDING", ScamCategory.PHISHING, Platform.SMS, ReportStatus.PENDING, 65, False, 2),
            ("SCM-DEMO-REJECT1", ScamCategory.OTHER, Platform.OTHER, ReportStatus.REJECTED, 15, False, None),
        ]

        for ref, cat, plat, status, score, is_high, vi_idx in demo_reports:
            report = ScamReport.objects.create(
                reference_code=ref,
                reporter=citizen if ref != "SCM-DEMO-REJECT1" else None,
                status=status,
                category=cat,
                platform=plat,
                message_text=f"Sample scam message narrative for {ref}.",
                financial_loss=Decimal("1500.00") if cat == ScamCategory.FAKE_JOB else Decimal("0.00"),
                currency="MYR",
                country_code="MY",
                risk_score=score,
                is_high_priority=is_high,
                created_at=timezone.now() - timezone.timedelta(days=2),
            )

            if vi_idx is not None and vi_idx < len(vis):
                vi = vis[vi_idx]
                ReportIndicator.objects.create(
                    report=report,
                    type=vi.type,
                    raw_value=vi.display_value,
                    normalized_value=vi.normalized_value,
                    display_value=vi.display_value,
                    verified_indicator=vi if status == ReportStatus.VERIFIED else None,
                )

            # Add an unverified indicator for pending report
            if status == ReportStatus.PENDING:
                norm_p, disp_p = normalize_phone("+60129876543", country_code="MY")
                ReportIndicator.objects.create(
                    report=report,
                    type=IndicatorType.PHONE,
                    raw_value="+60129876543",
                    normalized_value=norm_p,
                    display_value=disp_p,
                )

    def _seed_advisories(self, analyst: User):
        if ThreatAdvisory.objects.filter(title__startswith="[Demo]").exists():
            return

        advisories_data = [
            (
                "[Demo] Emergency Warning: Fake Banking Credential SMS",
                "Severe surge in spoofed bank SMS messages with urgent account suspension threats.",
                AdvisorySeverity.CRITICAL,
                AudienceGroup.GENERAL.value,
                AdvisoryStatus.PUBLISHED,
                True,
            ),
            (
                "[Demo] Alert: Fake Job Task Scams on Messaging Platforms",
                "Scammers targeting young jobseekers with promises of daily commission for app reviews.",
                AdvisorySeverity.WARNING,
                AudienceGroup.TEENAGER.value,
                AdvisoryStatus.PUBLISHED,
                True,
            ),
            (
                "[Demo] Draft: Emerging QR Code Tampering Advisory",
                "Preliminary investigation into malicious QR codes placed over legitimate merchant displays.",
                AdvisorySeverity.INFO,
                AudienceGroup.GENERAL.value,
                AdvisoryStatus.DRAFT,
                False,
            ),
        ]

        for title, summary, sev, aud, status, published in advisories_data:
            ThreatAdvisory.objects.create(
                title=title,
                body=summary,
                severity=sev,
                target_audience=aud,
                status=status,
                created_by=analyst,
                published_by=analyst if published else None,
                published_at=timezone.now() - timezone.timedelta(days=1) if published else None,
            )

    def _seed_simulator_attempts(self, citizen: User, educator: User):
        if SimulatorAttempt.objects.exists():
            return

        scenarios = list(SimulatorScenario.objects.filter(status=ScenarioStatus.PUBLISHED)[:5])
        if len(scenarios) < 5:
            # Create filler published scenarios if seed_scenarios did not provide 5
            for i in range(5 - len(scenarios)):
                sc = SimulatorScenario.objects.create(
                    title=f"Demo Scenario Auto {i}",
                    channel="EMAIL",
                    is_scam=False,
                    tactic="NONE",
                    difficulty=1,
                    image_s3_key=f"scenarios/demo_filler_{i}.png",
                    image_alt="Legitimate communication",
                    explanation="Verified valid communication.",
                    status=ScenarioStatus.PUBLISHED,
                    author=educator,
                )
                scenarios.append(sc)

        scenario_ids = [s.id for s in scenarios]

        # 1. In-progress attempt
        SimulatorAttempt.objects.create(
            user=citizen,
            session_key=uuid.uuid4(),
            status=AttemptStatus.IN_PROGRESS,
            scenario_ids=scenario_ids,
            started_at=timezone.now(),
        )

        # 2. Completed attempt with answers
        comp_attempt = SimulatorAttempt.objects.create(
            user=citizen,
            session_key=uuid.uuid4(),
            status=AttemptStatus.COMPLETED,
            scenario_ids=scenario_ids,
            score_pct=80,
            profile={"URGENCY": {"correct": 2, "total": 2}},
            started_at=timezone.now() - timezone.timedelta(minutes=15),
            completed_at=timezone.now(),
        )

        for sc in scenarios:
            AttemptAnswer.objects.create(
                attempt=comp_attempt,
                scenario=sc,
                answered_is_scam=sc.is_scam,
                selected_flag_code=None if not sc.is_scam else "ARTIFICIAL_URGENCY",
                is_correct=True,
            )

    def _seed_audit_logs(self, admin: User):
        if SystemAuditLog.objects.exists():
            return

        events = [
            (AuditEventType.USER_REGISTERED, AuditSeverity.INFO, "User registered demo account"),
            (AuditEventType.LOGIN_SUCCESS, AuditSeverity.INFO, "Successful admin portal login"),
            (AuditEventType.REPORT_SUBMITTED, AuditSeverity.INFO, "Citizen submitted scam report"),
            (AuditEventType.INDICATOR_VERIFIED, AuditSeverity.ALERT, "Analyst verified malicious indicator"),
        ]

        for etype, sev, note in events:
            SystemAuditLog.objects.create(
                event_type=etype,
                severity=sev,
                actor=admin,
                actor_ip_hash="a" * 64,
                metadata={"note": note},
            )

    def _seed_load_scale_data(self):
        self.stdout.write("Generating load-scale data (20,000 reports, 20,000 indicators, 50,000 audit logs)...")

        batch_size = 5000
        total_reports = 20000
        total_audit = 50000

        # Bulk create reports
        report_objs = []
        now = timezone.now()
        for i in range(total_reports):
            report_objs.append(
                ScamReport(
                    id=uuid.uuid4(),
                    reference_code=f"SCM-LOAD-{i:07d}",
                    status=ReportStatus.PENDING if i % 2 == 0 else ReportStatus.VERIFIED,
                    category=ScamCategory.PHISHING if i % 3 == 0 else ScamCategory.FAKE_JOB,
                    platform=Platform.WHATSAPP if i % 2 == 0 else Platform.EMAIL,
                    message_text=f"Load test generated scam narrative sample {i}.",
                    financial_loss=Decimal("250.00") if i % 4 == 0 else Decimal("0.00"),
                    currency="MYR",
                    country_code="MY",
                    risk_score=(i % 100),
                    is_high_priority=(i % 100 >= 75),
                    created_at=now - timezone.timedelta(days=(i % 60)),
                )
            )

        ScamReport.objects.bulk_create(report_objs, batch_size=batch_size)
        self.stdout.write(f"Created {len(report_objs)} reports.")

        # Bulk create indicators
        indicator_objs = []
        for i, rep in enumerate(report_objs):
            indicator_objs.append(
                ReportIndicator(
                    report=rep,
                    type=IndicatorType.PHONE if i % 2 == 0 else IndicatorType.DOMAIN,
                    raw_value=f"+601900{i:06d}" if i % 2 == 0 else f"load-domain-{i:06d}.com",
                    normalized_value=f"+601900{i:06d}" if i % 2 == 0 else f"load-domain-{i:06d}.com",
                    display_value=f"+601900{i:06d}" if i % 2 == 0 else f"load-domain-{i:06d}.com",
                )
            )

        ReportIndicator.objects.bulk_create(indicator_objs, batch_size=batch_size)
        self.stdout.write(f"Created {len(indicator_objs)} report indicators.")

        # Bulk create audit logs
        audit_objs = []
        for i in range(total_audit):
            audit_objs.append(
                SystemAuditLog(
                    event_type=AuditEventType.REPORT_SUBMITTED if i % 2 == 0 else AuditEventType.LOGIN_SUCCESS,
                    severity=AuditSeverity.INFO if i % 5 != 0 else AuditSeverity.WARN,
                    actor_ip_hash=f"{i % 1000:064x}",
                    metadata={"load_batch": i // batch_size},
                    occurred_at=now - timezone.timedelta(days=(i % 30)),
                )
            )

        SystemAuditLog.objects.bulk_create(audit_objs, batch_size=batch_size)
        self.stdout.write(f"Created {len(audit_objs)} audit logs.")
