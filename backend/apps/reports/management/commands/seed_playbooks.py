import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.reports.models import RecoveryPlaybook

logger = logging.getLogger(__name__)


def load_hotlines_data(data_dir: Path) -> dict:
    """
    Loads apps/reports/data/hotlines.json if present per D77.
    Returns mapping of country_code to hotline list, or empty dict.
    """
    hotlines_path = data_dir / "hotlines.json"
    if not hotlines_path.exists():
        return {}
    try:
        with open(hotlines_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to load hotlines.json: %s", exc)
        return {}


class Command(BaseCommand):
    help = "Idempotently seeds RecoveryPlaybook rows from playbooks.json per D77."

    def handle(self, *args, **options):
        data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        playbooks_path = data_dir / "playbooks.json"

        if not playbooks_path.exists():
            self.stderr.write(self.style.ERROR(f"playbooks.json not found at {playbooks_path}"))
            return

        with open(playbooks_path, encoding="utf-8") as f:
            playbooks_data = json.load(f)

        hotlines_map = load_hotlines_data(data_dir)

        created_count = 0
        updated_count = 0

        for item in playbooks_data:
            cat = item.get("category")
            pay = item.get("payment_method")
            country = item.get("country_code")
            title = item.get("title", "")
            steps = item.get("steps", [])
            priority = item.get("priority", 0)

            # Resolve hotlines if supplied in hotlines.json
            item_hotlines = []
            if country and country in hotlines_map:
                item_hotlines = hotlines_map[country]
            elif "default" in hotlines_map:
                item_hotlines = hotlines_map["default"]

            obj, created = RecoveryPlaybook.objects.update_or_create(
                category=cat,
                payment_method=pay,
                country_code=country,
                defaults={
                    "title": title,
                    "steps": steps,
                    "hotlines": item_hotlines,
                    "priority": priority,
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed completed: {created_count} created, {updated_count} updated "
                f"({len(playbooks_data)} total active playbooks)."
            )
        )
