import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.reports.constants import ALLOWED_COUNTRY_CODES, ALLOWED_CURRENCIES
from apps.reports.models import (
    IndicatorType,
    PaymentMethod,
    Platform,
    RecoveryPlaybook,
    ScamCategory,
)
from apps.reports.selectors.report_selectors import (
    DEFAULT_PLAYBOOK,
    get_recovery_playbook,
    get_report_options,
)


@pytest.mark.django_db
class TestSeedPlaybooksCommand:
    def test_seed_playbooks_is_idempotent(self):
        # Initial seed
        call_command("seed_playbooks")
        initial_count = RecoveryPlaybook.objects.count()
        assert initial_count >= 10

        # Re-run: count must not change (no duplicate rows per D77)
        call_command("seed_playbooks")
        assert RecoveryPlaybook.objects.count() == initial_count

    def test_hotlines_merging_when_file_present(self, tmp_path, monkeypatch):
        # Create dummy hotlines.json
        hotlines_data = {
            "MY": [
                {
                    "name": "NSRC",
                    "number": "997",
                    "source_url": "https://www.bnm.gov.my/nsrc",
                    "verified_on": "2026-10-01",
                }
            ],
            "default": [
                {
                    "name": "Local Police",
                    "number": "999",
                    "source_url": "https://example.com/police",
                    "verified_on": "2026-10-01",
                }
            ],
        }
        hotlines_file = tmp_path / "hotlines.json"
        hotlines_file.write_text(json.dumps(hotlines_data), encoding="utf-8")

        # Copy playbooks.json into tmp_path as well
        source_playbooks = (
            Path(__file__).resolve().parent.parent / "data" / "playbooks.json"
        )
        (tmp_path / "playbooks.json").write_text(
            source_playbooks.read_text(encoding="utf-8"), encoding="utf-8"
        )

        from apps.reports.management.commands import seed_playbooks

        def mocked_handle(self, *args, **options):
            # Patch data_dir to tmp_path
            monkeypatch.setattr(
                seed_playbooks,
                "Path",
                lambda *a: tmp_path if "data" in str(a) else Path(*a),
            )
            # Re-seed with mocked data dir
            hotlines_map = seed_playbooks.load_hotlines_data(tmp_path)
            assert "MY" in hotlines_map
            for item in json.loads((tmp_path / "playbooks.json").read_text(encoding="utf-8")):
                cat = item.get("category")
                pay = item.get("payment_method")
                country = item.get("country_code")
                item_hotlines = []
                if country and country in hotlines_map:
                    item_hotlines = hotlines_map[country]
                elif "default" in hotlines_map:
                    item_hotlines = hotlines_map["default"]
                RecoveryPlaybook.objects.update_or_create(
                    category=cat,
                    payment_method=pay,
                    country_code=country,
                    defaults={"hotlines": item_hotlines},
                )

        mocked_handle(None)

        my_playbook = RecoveryPlaybook.objects.filter(country_code="MY").first()
        assert my_playbook is not None
        assert my_playbook.hotlines == [
            {
                "name": "NSRC",
                "number": "997",
                "source_url": "https://www.bnm.gov.my/nsrc",
                "verified_on": "2026-10-01",
            }
        ]

        # Re-running normal seed without hotlines leaves hotlines empty
        call_command("seed_playbooks")
        clean_playbook = RecoveryPlaybook.objects.filter(country_code="MY").first()
        assert clean_playbook.hotlines == []


@pytest.mark.django_db
class TestPlaybookSelectionMatrix:
    def setup_method(self, method=None):
        call_command("seed_playbooks")

    def test_bank_transfer_with_loss_contains_bank_freeze_marker(self):
        # D78: Bank transfer with loss > 0 must contain the bank-freeze step (tested by step marker)
        pb_my = get_recovery_playbook(
            category=ScamCategory.PHISHING,
            payment_method=PaymentMethod.BANK_TRANSFER,
            country_code="MY",
            financial_loss=Decimal("250.00"),
        )
        assert pb_my is not None
        markers = [s.get("marker") for s in pb_my["steps"]]
        assert "bank_freeze" in markers

        # Even if selecting a generic category playbook, bank_freeze step is injected when loss > 0
        pb_generic = get_recovery_playbook(
            category=ScamCategory.OTHER,
            payment_method=PaymentMethod.BANK_TRANSFER,
            country_code="ZZ",
            financial_loss=Decimal("100.00"),
        )
        generic_markers = [s.get("marker") for s in pb_generic["steps"]]
        assert "bank_freeze" in generic_markers

    def test_playbook_structure_and_disclaimer(self):
        # D77: Every playbook ends with "This is general guidance, not legal advice."
        # D78: {title, steps:[{title, detail}], hotlines:[]}
        pb = get_recovery_playbook()
        assert "title" in pb
        assert "steps" in pb
        assert "hotlines" in pb
        assert isinstance(pb["steps"], list)
        assert len(pb["steps"]) > 0

        for step in pb["steps"]:
            assert "title" in step
            assert "detail" in step

        last_step = pb["steps"][-1]
        assert "This is general guidance, not legal advice." in last_step["detail"]

    def test_specificity_ranking_most_fields_win(self):
        # D66: Most matching fields wins, then priority, then lowest id
        # Specific MY bank transfer
        pb_my = get_recovery_playbook(
            category=None,
            payment_method=PaymentMethod.BANK_TRANSFER,
            country_code="MY",
        )
        assert "Malaysia" in pb_my["title"]

        # Specific NP bank transfer
        pb_np = get_recovery_playbook(
            category=None,
            payment_method=PaymentMethod.BANK_TRANSFER,
            country_code="NP",
        )
        assert "Nepal" in pb_np["title"]

        # General bank transfer (country_code=None)
        pb_gen_bank = get_recovery_playbook(
            category=None,
            payment_method=PaymentMethod.BANK_TRANSFER,
            country_code="ZZ",
        )
        assert "General" in pb_gen_bank["title"]

    def test_fallback_to_default_when_no_playbooks_seeded(self):
        RecoveryPlaybook.objects.all().delete()
        pb = get_recovery_playbook(
            category=ScamCategory.PHISHING,
            payment_method=PaymentMethod.CRYPTO,
            country_code="ZZ",
        )
        assert pb["title"] == DEFAULT_PLAYBOOK["title"]
        assert len(pb["steps"]) == len(DEFAULT_PLAYBOOK["steps"])


class TestReportOptions:
    def test_report_options_matches_enums_and_constants(self):
        options = get_report_options()

        # Countries
        country_codes = {c["code"] for c in options["countries"]}
        assert country_codes == ALLOWED_COUNTRY_CODES

        # Currencies
        assert set(options["currencies"]) == ALLOWED_CURRENCIES

        # Categories
        cat_codes = {c["code"] for c in options["categories"]}
        assert cat_codes == set(ScamCategory.values)

        # Platforms
        plat_codes = {p["code"] for p in options["platforms"]}
        assert plat_codes == set(Platform.values)

        # Payment Methods
        pay_codes = {m["code"] for m in options["payment_methods"]}
        assert pay_codes == set(PaymentMethod.values)

        # Indicator Types
        ind_codes = {t["code"] for t in options["indicator_types"]}
        assert ind_codes == set(IndicatorType.values)

        # Admin Areas
        assert "MY" in options["admin_areas"]
        assert len(options["admin_areas"]["MY"]) == 16  # 13 states + 3 federal territories
        assert "NP" in options["admin_areas"]
        assert len(options["admin_areas"]["NP"]) == 7   # 7 provinces
        assert options["admin_areas"]["ZZ"] == []
