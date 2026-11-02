from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import ApprovalStatus, Role, User
from apps.core.enums import AudienceGroup
from apps.literacy.models import ContentStatus, EducationalGuide, Language, ReadabilityMode, Tactic

CURRICULUM_GUIDES = [
    {
        "slug": "phishing-awareness-and-email-verification",
        "title": "Phishing Awareness: How to Verify Suspicious Emails",
        "summary": "Learn how to spot forged sender addresses, deceptive links, and urgent language commonly found in phishing campaigns.",
        "body": """# Identifying Phishing Emails

Phishing is one of the most common cyber attack vectors. Scammers try to trick you into revealing personal information or financial credentials.

## Red Flags to Watch For
1. **Urgent or Threatening Language**: Demands immediate action to avoid penalty or account suspension.
2. **Mismatched Sender Addresses**: The display name looks legitimate, but the actual email address is forged or misspelled.
3. **Generic Greetings**: "Dear Customer" instead of your actual name.
4. **Suspicious Links and Attachments**: Hover over links before clicking to check the destination URL.

## What You Should Do
- Never click on unsolicited links or download unexpected attachments.
- Navigate directly to official websites by typing the address yourself.
- Report suspicious emails through the ScamShield platform.
""",
        "audience_groups": [AudienceGroup.GENERAL.value, AudienceGroup.TEENAGER.value],
        "tactics": [Tactic.URGENCY.value, Tactic.AUTHORITY.value],
        "language": Language.EN.value,
        "readability_mode": ReadabilityMode.STANDARD.value,
    },
    {
        "slug": "elderly-phone-and-sms-scam-protection",
        "title": "Seniors & Family: Protecting Against Impersonation Calls",
        "summary": "Clear, accessible guidance for seniors and family caregivers to identify and halt government or bank impersonation phone scams.",
        "body": """# Phone and SMS Scam Protection for Seniors

Scammers frequently target seniors by pretending to be government officials, police officers, or bank staff.

## Key Safety Rules
1. **Government officials will NEVER ask for your banking passwords or OTP over the phone.**
2. **Never transfer money to a 'safe account' during an unexpected phone call.**
3. **Hang up immediately if anyone pressures you to act quickly.**

## How Families Can Help
- Discuss scam tactics openly with parents and grandparents.
- Assist family members with setting up call blocking features.
- Help report suspected scams on ScamShield to protect others in the community.
""",
        "audience_groups": [AudienceGroup.ELDERLY.value, AudienceGroup.GENERAL.value],
        "tactics": [Tactic.AUTHORITY.value, Tactic.FEAR.value, Tactic.URGENCY.value],
        "language": Language.EN.value,
        "readability_mode": ReadabilityMode.LARGE_HIGH_CONTRAST.value,
    },
    {
        "slug": "lottery-and-prize-scams-nepali",
        "title": "चिट्ठा तथा पुरस्कार ठगीबाट बच्ने उपायहरू (Lottery Scam Protection)",
        "summary": "नेपाली समुदायका लागि चिट्ठा, उपहार, र नक्कली पुरस्कार ठगी पहिचान गर्ने र सुरक्षित रहने आवश्यक जानकारी।",
        "body": """# नक्कली चिट्ठा र पुरस्कार ठगीबाट सतर्क रहनुहोस्

अपरिचित व्यक्ति वा सन्देशले तपाईंलाई ठूलो रकम वा महँगो उपहार परेको दाबी गर्न सक्छ।

## मुख्य लक्षणहरू
- तपाईंले भाग नै नलिएको चिट्ठामा पुरस्कार परेको भनिनु।
- पुरस्कार पाउनका लागि अग्रिम शुल्क, कर, वा सेवा शुल्क तिर्न माग गरिनु।
- तपाईंको बैंक खाता नम्बर वा गोप्य कोड (OTP) माग्नु।

## सुरक्षाका उपायहरू
- कुनै पनि अपरिचित व्यक्तिलाई पैसा नपठाउनुहोस्।
- आफ्नो व्यक्तिगत जानकारी गोप्य राख्नुहोस्।
- शंकास्पद फोन वा सन्देश आएमा तुरून्त ScamShield मा सूचना दिनुहोस्।
""",
        "audience_groups": [AudienceGroup.ELDERLY.value, AudienceGroup.NON_TECH.value, AudienceGroup.GENERAL.value],
        "tactics": [Tactic.GREED.value, Tactic.URGENCY.value],
        "language": Language.NE.value,
        "readability_mode": ReadabilityMode.STANDARD.value,
    },
    {
        "slug": "panduan-keselamatan-scam-pelaburan-malay",
        "title": "Panduan Keselamatan: Mengenali Penipuan Pelaburan Tidak Wujud",
        "summary": "Ketahui cara mengenal pasti skim pelaburan palsu yang menjanjikan pulangan luar biasa tinggi dalam masa singkat.",
        "body": """# Lindungi Diri Daripada Penipuan Pelaburan

Skim pelaburan palsu sering memikat mangsa dengan janji pulangan lumayan tanpa sebarang risiko kerugian.

## Tanda-tanda Amaran Penipuan
1. **Janji Pulangan Tidak Munasabah**: Menawarkan keuntungan berlipat ganda dalam masa beberapa hari atau minggu.
2. **Tekanan Untuk Melabur Cepat**: Menyatakan bahawa peluang keemasan akan terlepas jika tidak melabur segera.
3. **Akaun Bank Perseorangan**: Wang pelaburan diminta dipindahkan ke akaun bank individu ('keldai akaun').

## Langkah Pencegahan
- Semak status lesen syarikat melalui saluran pihak berkuasa kewangan rasmi.
- Jangan sesekali menyerahkan wang atau maklumat perbankan kepada individu yang tidak dikenali.
- Laporkan sebarang cubaan penipuan kepada ScamShield dengan segera.
""",
        "audience_groups": [AudienceGroup.GENERAL.value, AudienceGroup.NON_TECH.value],
        "tactics": [Tactic.GREED.value, Tactic.URGENCY.value],
        "language": Language.MS.value,
        "readability_mode": ReadabilityMode.STANDARD.value,
    },
]


class Command(BaseCommand):
    help = "Seeds initial multilingual educational guides for the literacy hub (idempotent)."

    def handle(self, *args, **options):
        author, _ = User.objects.get_or_create(
            email="curriculum@scamshield.gov.sg",
            defaults={
                "role": Role.EDUCATOR,
                "approval_status": ApprovalStatus.APPROVED,
            },
        )

        now = timezone.now()
        created_count = 0
        updated_count = 0

        for item in CURRICULUM_GUIDES:
            guide, created = EducationalGuide.objects.get_or_create(
                slug=item["slug"],
                defaults={
                    "title": item["title"],
                    "summary": item["summary"],
                    "body": item["body"],
                    "audience_groups": item["audience_groups"],
                    "tactics": item["tactics"],
                    "language": item["language"],
                    "readability_mode": item["readability_mode"],
                    "status": ContentStatus.PUBLISHED.value,
                    "published_at": now,
                    "author": author,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded educational guides: {created_count} created, {updated_count} existing."
            )
        )
