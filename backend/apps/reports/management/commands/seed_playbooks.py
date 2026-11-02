import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.reports.models import RecoveryPlaybook

logger = logging.getLogger(__name__)


def load_hotlines_data(data_dir: Path) -> dict:
    """
    Loads apps/reports/data/hotlines.json if present per D77 and D135.
    Validates each entry to require name, number, source_url, verified_on.
    Refuses and logs warning for any entry lacking source_url or verified_on.
    Returns mapping of country_code to validated hotline list.
    """
    hotlines_path = data_dir / "hotlines.json"
    if not hotlines_path.exists():
        return {}
    try:
        with open(hotlines_path, encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as exc:
        logger.warning("Failed to load hotlines.json: %s", exc)
        return {}

    if not isinstance(raw_data, dict):
        logger.warning("hotlines.json root must be a dict mapping country codes")
        return {}

    validated = {}
    for country, entries in raw_data.items():
        if not isinstance(entries, list):
            logger.warning("hotlines entries for %s must be a list", country)
            continue
        valid_entries = []
        for item in entries:
            if not isinstance(item, dict):
                logger.warning("Refusing non-dict hotline entry for %s: %s", country, item)
                continue
            name = item.get("name")
            number = item.get("number")
            source_url = item.get("source_url")
            verified_on = item.get("verified_on")

            if not (source_url and str(source_url).strip()) or not (
                verified_on and str(verified_on).strip()
            ):
                logger.warning(
                    "Refusing hotline entry for %s lacking source_url or verified_on: %s",
                    country,
                    item,
                )
                continue

            if not (name and str(name).strip()) or not (number and str(number).strip()):
                logger.warning(
                    "Refusing hotline entry for %s lacking name or number: %s",
                    country,
                    item,
                )
                continue

            valid_entries.append(
                {
                    "name": str(name).strip(),
                    "number": str(number).strip(),
                    "source_url": str(source_url).strip(),
                    "verified_on": str(verified_on).strip(),
                }
            )
        validated[country] = valid_entries

    return validated


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
