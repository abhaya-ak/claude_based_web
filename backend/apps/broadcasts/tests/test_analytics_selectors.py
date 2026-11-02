from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.broadcasts.selectors.analytics_selectors import (
    calculate_spike_status,
    get_losses_analytics,
    get_spikes_analytics,
    get_tactics_analytics,
    get_volume_analytics,
    validate_date_range,
)
from apps.reports.models import Platform, ScamCategory, ScamReport
from apps.scanner.models import ScanResult


class TestDateRangeValidation:
    def test_default_trailing_30_days(self):
        today = timezone.now().date()
        start, end = validate_date_range(None, None)
        assert end == today
        assert start == today - timedelta(days=30)

    def test_valid_custom_date_range(self):
        start, end = validate_date_range("2026-09-01", "2026-09-30")
        assert start == date(2026, 9, 1)
        assert end == date(2026, 9, 30)

    def test_start_after_end_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc:
            validate_date_range("2026-10-15", "2026-10-01")
        assert "start_date" in str(exc.value) or "before" in str(exc.value)

    def test_range_exceeding_90_days_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc:
            validate_date_range("2026-01-01", "2026-04-15")  # 104 days
        assert "90 days" in str(exc.value) or "date_range" in str(exc.value)

    def test_invalid_date_format_raises_validation_error(self):
        with pytest.raises(ValidationError):
            validate_date_range("invalid-date", "2026-10-01")


@pytest.mark.django_db
class TestVolumeAnalyticsSelector:
    def test_volume_aggregation_with_fixed_fixtures(self):
        base_date = timezone.now().date() - timedelta(days=5)

        # Create reports across 2 days, 2 platforms, 2 categories
        r1 = ScamReport.objects.create(
            reference_code="SCM-2026-VOL001",
            category=ScamCategory.PHISHING,
            platform=Platform.WHATSAPP,
            country_code="MY",
            admin_area="KUL",
        )
        dt1 = timezone.make_aware(datetime.combine(base_date, datetime.min.time()))
        ScamReport.objects.filter(id=r1.id).update(created_at=dt1)

        r2 = ScamReport.objects.create(
            reference_code="SCM-2026-VOL002",
            category=ScamCategory.PHISHING,
            platform=Platform.TELEGRAM,
            country_code="MY",
            admin_area="SGR",
        )
        ScamReport.objects.filter(id=r2.id).update(created_at=dt1)

        r3 = ScamReport.objects.create(
            reference_code="SCM-2026-VOL003",
            category=ScamCategory.FAKE_JOB,
            platform=Platform.TELEGRAM,
            country_code="MY",
            admin_area="KUL",
        )
        dt2 = timezone.make_aware(datetime.combine(base_date + timedelta(days=1), datetime.min.time()))
        ScamReport.objects.filter(id=r3.id).update(created_at=dt2)

        res = get_volume_analytics(base_date - timedelta(days=1), base_date + timedelta(days=2))

        assert res["total_reports"] == 3
        # Check by_platform
        plat_map = {item["platform"]: item["count"] for item in res["by_platform"]}
        assert plat_map.get(Platform.TELEGRAM) == 2
        assert plat_map.get(Platform.WHATSAPP) == 1

        # Check by_category
        cat_map = {item["category"]: item["count"] for item in res["by_category"]}
        assert cat_map.get(ScamCategory.PHISHING) == 2
        assert cat_map.get(ScamCategory.FAKE_JOB) == 1

        # Check by_day
        day_map = {str(item["date"]): item["count"] for item in res["by_day"]}
        assert day_map.get(str(base_date)) == 2
        assert day_map.get(str(base_date + timedelta(days=1))) == 1


@pytest.mark.django_db
class TestLossesAnalyticsSelector:
    def test_losses_aggregation_grouped_by_currency_and_geo(self):
        start = timezone.now().date() - timedelta(days=10)
        end = timezone.now().date()

        # MYR losses in KUL and SGR
        ScamReport.objects.create(
            reference_code="SCM-2026-LOSS01",
            category=ScamCategory.FAKE_JOB,
            platform=Platform.WHATSAPP,
            country_code="MY",
            admin_area="KUL",
            financial_loss=Decimal("15000.50"),
            currency="MYR",
        )
        ScamReport.objects.create(
            reference_code="SCM-2026-LOSS02",
            category=ScamCategory.FAKE_JOB,
            platform=Platform.WHATSAPP,
            country_code="MY",
            admin_area="KUL",
            financial_loss=Decimal("5000.00"),
            currency="MYR",
        )
        ScamReport.objects.create(
            reference_code="SCM-2026-LOSS03",
            category=ScamCategory.ECOMMERCE_FRAUD,
            platform=Platform.FACEBOOK,
            country_code="MY",
            admin_area="SGR",
            financial_loss=Decimal("250.00"),
            currency="MYR",
        )

        # NPR loss in BAG
        ScamReport.objects.create(
            reference_code="SCM-2026-LOSS04",
            category=ScamCategory.FAKE_JOB,
            platform=Platform.TELEGRAM,
            country_code="NP",
            admin_area="BAG",
            financial_loss=Decimal("80000.00"),
            currency="NPR",
        )

        # Zero loss report
        ScamReport.objects.create(
            reference_code="SCM-2026-LOSS05",
            category=ScamCategory.PHISHING,
            platform=Platform.EMAIL,
            country_code="MY",
            admin_area="KUL",
            financial_loss=Decimal("0.00"),
            currency="MYR",
        )

        losses = get_losses_analytics(start, end)

        # Find MY / KUL / MYR
        kul_myr = next(
            (
                x
                for x in losses
                if x["country_code"] == "MY" and x["admin_area"] == "KUL" and x["currency"] == "MYR"
            ),
            None,
        )
        assert kul_myr is not None
        assert kul_myr["total_loss"] == Decimal("20000.50")
        assert kul_myr["report_count"] == 3  # including 0 loss report

        # Find NP / BAG / NPR
        bag_npr = next(
            (
                x
                for x in losses
                if x["country_code"] == "NP" and x["admin_area"] == "BAG" and x["currency"] == "NPR"
            ),
            None,
        )
        assert bag_npr is not None
        assert bag_npr["total_loss"] == Decimal("80000.00")
        assert bag_npr["report_count"] == 1


@pytest.mark.django_db
class TestTacticsAnalyticsSelector:
    def test_tactics_extraction_from_scan_breakdown_and_fallback(self):
        start = timezone.now().date() - timedelta(days=5)
        end = timezone.now().date()

        # Report 1 with ScanResult keyword breakdown: "urgent" -> URGENCY
        r1 = ScamReport.objects.create(
            reference_code="SCM-2026-TAC01",
            category=ScamCategory.PHISHING,
            platform=Platform.EMAIL,
            country_code="MY",
        )
        ScanResult.objects.create(
            report=r1,
            ruleset_version=1,
            risk_score=60,
            is_high_priority=False,
            breakdown=[{"rule": "urgent", "type": "KEYWORD", "points": 15}],
        )

        # Report 2 with ScanResult keyword breakdown: "arrest" -> FEAR, "police" -> AUTHORITY
        r2 = ScamReport.objects.create(
            reference_code="SCM-2026-TAC02",
            category=ScamCategory.IMPERSONATION,
            platform=Platform.SMS,
            country_code="MY",
        )
        ScanResult.objects.create(
            report=r2,
            ruleset_version=1,
            risk_score=75,
            is_high_priority=True,
            breakdown=[
                {"rule": "arrest", "type": "KEYWORD", "points": 15},
                {"rule": "police", "type": "KEYWORD", "points": 15},
            ],
        )

        # Report 3 without ScanResult: fallback to category FAKE_JOB -> GREED
        ScamReport.objects.create(
            reference_code="SCM-2026-TAC03",
            category=ScamCategory.FAKE_JOB,
            platform=Platform.TELEGRAM,
            country_code="MY",
        )

        tactics = get_tactics_analytics(start, end)
        tactic_map = {item["tactic"]: item["count"] for item in tactics}

        assert tactic_map.get("URGENCY", 0) >= 1
        assert tactic_map.get("FEAR", 0) >= 1
        assert tactic_map.get("AUTHORITY", 0) >= 1
        assert tactic_map.get("GREED", 0) >= 1


class TestSpikeMathBoundaries:
    @pytest.mark.parametrize(
        "daily_avg,last_24h,expected_spike,expected_growth",
        [
            # 1. 0 trailing count & 4 in 24h -> is_spike=False (< 5 noise filter)
            (0.0, 4, False, None),
            # 2. 0 trailing count & 5 in 24h -> is_spike=True (new outbreak >= 5)
            (0.0, 5, True, None),
            # 3. 10 daily avg & 20 in 24h (+100%) -> is_spike=False
            (10.0, 20, False, 100.0),
            # 4. 10 daily avg & 40 in 24h (+300%) -> is_spike=True
            (10.0, 40, True, 300.0),
            # 5. 2 daily avg & 30 in 24h (+1400%) -> is_spike=True
            (2.0, 30, True, 1400.0),
            # 6. Steady volume (10 avg vs 10 in 24h -> 0% growth) -> is_spike=False
            (10.0, 10, False, 0.0),
        ],
    )
    def test_spike_math_boundary_table(self, daily_avg, last_24h, expected_spike, expected_growth):
        is_spike, growth_pct = calculate_spike_status(last_24h, daily_avg)
        assert is_spike == expected_spike
        if expected_growth is not None:
            assert growth_pct == expected_growth


@pytest.mark.django_db
class TestSpikesAnalyticsDatabaseSelector:
    def test_database_spikes_detection_matches_time_windows(self):
        ref_time = timezone.now()

        # Create 5 reports in the last 24h for TELEGRAM / FAKE_JOB
        for i in range(5):
            r = ScamReport.objects.create(
                reference_code=f"SCM-2026-SPK{i}",
                category=ScamCategory.FAKE_JOB,
                platform=Platform.TELEGRAM,
                country_code="MY",
            )
            ScamReport.objects.filter(id=r.id).update(created_at=ref_time - timedelta(hours=2))

        # None in trailing 7 days
        spikes = get_spikes_analytics(reference_time=ref_time)
        tg_inv = next(
            (
                x
                for x in spikes
                if x["platform"] == Platform.TELEGRAM and x["category"] == ScamCategory.FAKE_JOB
            ),
            None,
        )
        assert tg_inv is not None
        assert tg_inv["last_24h_count"] == 5
        assert tg_inv["daily_avg"] == 0.0
        assert tg_inv["is_spike"] is True
