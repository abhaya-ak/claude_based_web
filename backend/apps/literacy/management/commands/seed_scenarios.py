import os
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounts.models import ApprovalStatus, Role, User
from apps.literacy.models import (
    RedFlagCode,
    ScenarioChannel,
    ScenarioRedFlag,
    ScenarioStatus,
    ScenarioTactic,
    SimulatorScenario,
)

SEED_SCENARIOS = [
    {
        "title": "Bank Account Suspension Alert",
        "channel": ScenarioChannel.SMS.value,
        "is_scam": True,
        "tactic": ScenarioTactic.URGENCY.value,
        "difficulty": 1,
        "image_s3_key": "scenarios/seed_bank_sms.png",
        "image_alt": "SMS warning account frozen unless verified within 15 minutes",
        "explanation": "Scammers manufacture urgency with artificial deadlines to induce panic.",
        "red_flags": [
            {
                "flag_code": RedFlagCode.ARTIFICIAL_URGENCY.value,
                "x_pct": Decimal("5.00"),
                "y_pct": Decimal("10.00"),
                "w_pct": Decimal("90.00"),
                "h_pct": Decimal("20.00"),
                "explanation": "Artificial 15-minute countdown to force hasty action.",
            },
            {
                "flag_code": RedFlagCode.SUSPICIOUS_LINK.value,
                "x_pct": Decimal("10.00"),
                "y_pct": Decimal("60.00"),
                "w_pct": Decimal("80.00"),
                "h_pct": Decimal("15.00"),
                "explanation": "Non-official shortened domain link.",
            },
        ],
    },
    {
        "title": "Federal Police Subpoena Notice",
        "channel": ScenarioChannel.EMAIL.value,
        "is_scam": True,
        "tactic": ScenarioTactic.AUTHORITY.value,
        "difficulty": 2,
        "image_s3_key": "scenarios/seed_police_subpoena.png",
        "image_alt": "Email pretending to be police headquarters citing criminal investigation",
        "explanation": "Impersonates law enforcement authority to coerce compliance.",
        "red_flags": [
            {
                "flag_code": RedFlagCode.AUTHORITY_IMPERSONATION.value,
                "x_pct": Decimal("5.00"),
                "y_pct": Decimal("5.00"),
                "w_pct": Decimal("90.00"),
                "h_pct": Decimal("25.00"),
                "explanation": "Forged official police logo and authority claims.",
            },
            {
                "flag_code": RedFlagCode.MISMATCHED_DOMAIN.value,
                "x_pct": Decimal("15.00"),
                "y_pct": Decimal("35.00"),
                "w_pct": Decimal("70.00"),
                "h_pct": Decimal("10.00"),
                "explanation": "Sender address is a public mail service, not official police domain.",
            },
        ],
    },
    {
        "title": "Immediate Tax Arrest Warrant",
        "channel": ScenarioChannel.SMS.value,
        "is_scam": True,
        "tactic": ScenarioTactic.FEAR.value,
        "difficulty": 2,
        "image_s3_key": "scenarios/seed_tax_warrant.png",
        "image_alt": "SMS alleging outstanding tax evasion with imminent police arrest",
        "explanation": "Weaponizes fear of criminal charges and arrest to intimidate victims.",
        "red_flags": [
            {
                "flag_code": RedFlagCode.THREAT_OF_LOSS.value,
                "x_pct": Decimal("10.00"),
                "y_pct": Decimal("20.00"),
                "w_pct": Decimal("80.00"),
                "h_pct": Decimal("25.00"),
                "explanation": "Threat of imminent arrest warrant without due process.",
            },
        ],
    },
    {
        "title": "High Yield Guaranteed Crypto Plan",
        "channel": ScenarioChannel.SOCIAL.value,
        "is_scam": True,
        "tactic": ScenarioTactic.GREED.value,
        "difficulty": 1,
        "image_s3_key": "scenarios/seed_crypto_plan.png",
        "image_alt": "Social media post promising 500% weekly guaranteed profit",
        "explanation": "Exploits greed with unrealistic, risk-free returns.",
        "red_flags": [
            {
                "flag_code": RedFlagCode.TOO_GOOD_TO_BE_TRUE.value,
                "x_pct": Decimal("10.00"),
                "y_pct": Decimal("30.00"),
                "w_pct": Decimal("80.00"),
                "h_pct": Decimal("30.00"),
                "explanation": "Guaranteed 500% returns in 7 days is mathematically impossible.",
            },
        ],
    },
    {
        "title": "Undelivered Courier Parcel Fee",
        "channel": ScenarioChannel.WHATSAPP.value,
        "is_scam": True,
        "tactic": ScenarioTactic.URGENCY.value,
        "difficulty": 1,
        "image_s3_key": "scenarios/seed_parcel_fee.png",
        "image_alt": "WhatsApp message asking for customs release fee for surprise parcel",
        "explanation": "Common phishing tactic claiming pending package delivery requiring fee payment.",
        "red_flags": [
            {
                "flag_code": RedFlagCode.SUSPICIOUS_LINK.value,
                "x_pct": Decimal("5.00"),
                "y_pct": Decimal("50.00"),
                "w_pct": Decimal("90.00"),
                "h_pct": Decimal("15.00"),
                "explanation": "Unregistered tracking portal domain.",
            },
        ],
    },
    {
        "title": "Corporate HR Payroll Verification",
        "channel": ScenarioChannel.EMAIL.value,
        "is_scam": True,
        "tactic": ScenarioTactic.AUTHORITY.value,
        "difficulty": 2,
        "image_s3_key": "scenarios/seed_hr_payroll.png",
        "image_alt": "Email pretending to be corporate HR requiring re-entering bank credentials",
        "explanation": "Phishing targeting employees by impersonating internal organizational departments.",
        "red_flags": [
            {
                "flag_code": RedFlagCode.REQUEST_FOR_SENSITIVE_DATA.value,
                "x_pct": Decimal("10.00"),
                "y_pct": Decimal("40.00"),
                "w_pct": Decimal("80.00"),
                "h_pct": Decimal("20.00"),
                "explanation": "Legitimate HR systems do not ask for banking login passwords via email.",
            },
        ],
    },
    {
        "title": "E-Wallet Instant Bonus Claim",
        "channel": ScenarioChannel.SMS.value,
        "is_scam": True,
        "tactic": ScenarioTactic.GREED.value,
        "difficulty": 1,
        "image_s3_key": "scenarios/seed_ewallet_bonus.png",
        "image_alt": "SMS announcing $500 free shopping voucher for immediate OTP confirmation",
        "explanation": "Baiting victims with free money to steal one-time authentication codes.",
        "red_flags": [
            {
                "flag_code": RedFlagCode.REQUEST_FOR_SENSITIVE_DATA.value,
                "x_pct": Decimal("5.00"),
                "y_pct": Decimal("45.00"),
                "w_pct": Decimal("90.00"),
                "h_pct": Decimal("20.00"),
                "explanation": "Demands entering OTP code to claim reward.",
            },
        ],
    },
    {
        "title": "Official Bank Monthly E-Statement",
        "channel": ScenarioChannel.EMAIL.value,
        "is_scam": False,
        "tactic": ScenarioTactic.NONE.value,
        "difficulty": 2,
        "image_s3_key": "scenarios/seed_legit_statement.png",
        "image_alt": "Standard monthly account statement notification from official bank domain",
        "explanation": "Legitimate advisory email containing no urgent links, threats, or login requests.",
        "red_flags": [],
    },
    {
        "title": "Telco Monthly Bill Confirmation",
        "channel": ScenarioChannel.SMS.value,
        "is_scam": False,
        "tactic": ScenarioTactic.NONE.value,
        "difficulty": 1,
        "image_s3_key": "scenarios/seed_legit_telco.png",
        "image_alt": "Informational SMS thanking customer for bill payment with receipt number",
        "explanation": "Standard informational receipt without clickable links or requests for information.",
        "red_flags": [],
    },
    {
        "title": "Government Portal Multi-Factor Authentication Alert",
        "channel": ScenarioChannel.WEBSITE.value,
        "is_scam": False,
        "tactic": ScenarioTactic.NONE.value,
        "difficulty": 2,
        "image_s3_key": "scenarios/seed_legit_gov_mfa.png",
        "image_alt": "Official government identity portal login screen with standard MFA prompt",
        "explanation": "Legitimate security prompt on official government domain.",
        "red_flags": [],
    },
]


class Command(BaseCommand):
    help = "Idempotently seed published simulator scenarios with hotspots"

    def handle(self, *args, **options):
        author = User.objects.filter(role__in=[Role.ADMIN, Role.EDUCATOR], approval_status=ApprovalStatus.APPROVED).first()
        if not author:
            author = User.objects.create_user(
                email="system_educator@scamshield.test",
                password=os.environ.get("SEED_DEMO_PASSWORD", "SystemPassword123!"),  # noqa: S106
                role=Role.EDUCATOR,
                approval_status=ApprovalStatus.APPROVED,
            )
            self.stdout.write(self.style.SUCCESS(f"Created fallback educator: {author.email}"))

        created_count = 0
        skipped_count = 0

        for sc_data in SEED_SCENARIOS:
            title = sc_data["title"]
            if SimulatorScenario.objects.filter(title=title).exists():
                skipped_count += 1
                continue

            scenario = SimulatorScenario.objects.create(
                title=title,
                channel=sc_data["channel"],
                is_scam=sc_data["is_scam"],
                tactic=sc_data["tactic"],
                difficulty=sc_data["difficulty"],
                image_s3_key=sc_data["image_s3_key"],
                image_alt=sc_data["image_alt"],
                explanation=sc_data["explanation"],
                status=ScenarioStatus.PUBLISHED,
                author=author,
            )

            for rf in sc_data["red_flags"]:
                ScenarioRedFlag.objects.create(
                    scenario=scenario,
                    flag_code=rf["flag_code"],
                    x_pct=rf["x_pct"],
                    y_pct=rf["y_pct"],
                    w_pct=rf["w_pct"],
                    h_pct=rf["h_pct"],
                    explanation=rf["explanation"],
                )

            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed simulator scenarios: {created_count} created, {skipped_count} already existed."
            )
        )
