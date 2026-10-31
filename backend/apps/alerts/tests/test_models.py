import pytest
from django.db import IntegrityError, transaction

from apps.accounts.tests.factories import UserFactory
from apps.alerts.models import (
    AlertSubscription,
    Channel,
    SubscriptionStatus,
)
from apps.alerts.tests.factories import AlertSubscriptionFactory
from apps.core.enums import AudienceGroup


@pytest.mark.django_db
class TestAlertSubscriptionConstraints:
    def test_duplicate_channel_endpoint_hash_audience_fails(self):
        """Failing-insert test for uq_sub_channel_endpoint_aud."""
        hash_val = "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
        AlertSubscriptionFactory(
            channel=Channel.EMAIL,
            endpoint_hash=hash_val,
            audience=AudienceGroup.GENERAL,
        )

        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AlertSubscriptionFactory(
                    channel=Channel.EMAIL,
                    endpoint_hash=hash_val,
                    audience=AudienceGroup.GENERAL,
                )
        assert "uq_sub_channel_endpoint_aud" in str(excinfo.value)

        # Positive control 1: distinct endpoint_hash succeeds
        distinct_hash = "9999222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
        sub1 = AlertSubscriptionFactory(
            channel=Channel.EMAIL,
            endpoint_hash=distinct_hash,
            audience=AudienceGroup.GENERAL,
        )
        assert sub1.id is not None

        # Positive control 2: same channel and endpoint_hash with DIFFERENT audience succeeds
        sub2 = AlertSubscriptionFactory(
            channel=Channel.EMAIL,
            endpoint_hash=hash_val,
            audience=AudienceGroup.ELDERLY,
        )
        assert sub2.id is not None
        assert sub2.audience == AudienceGroup.ELDERLY

    def test_categories_array_containment_constraint(self):
        """Amendment A: tests for ck_sub_categories_elements."""
        # 1. ["PHISHING"] ok
        sub_phish = AlertSubscriptionFactory(categories=["PHISHING"])
        assert sub_phish.categories == ["PHISHING"]

        # 2. ["PHISHING", "FAKE_JOB"] ok
        sub_multi = AlertSubscriptionFactory(categories=["PHISHING", "FAKE_JOB"])
        assert sub_multi.categories == ["PHISHING", "FAKE_JOB"]

        # 3. [] ok (empty array represents all categories)
        sub_empty = AlertSubscriptionFactory(categories=[])
        assert sub_empty.categories == []

        # 4. ["INVALID_CAT"] fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AlertSubscriptionFactory(categories=["INVALID_CAT"])
        assert "ck_sub_categories_elements" in str(excinfo.value)

        # 5. ["PHISHING", "INVALID_CAT"] fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AlertSubscriptionFactory(categories=["PHISHING", "INVALID_CAT"])
        assert "ck_sub_categories_elements" in str(excinfo.value)

        # 6. ["PHISHING", None] fails
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AlertSubscriptionFactory(categories=["PHISHING", None])
        assert "ck_sub_categories_elements" in str(excinfo.value)

    def test_new_subscription_without_categories_stores_empty_list_never_null(self):
        """Amendment C: saved without categories stores [] (never NULL)."""
        sub = AlertSubscription.objects.create(
            channel=Channel.SMS,
            endpoint="+60123456789",
            endpoint_hash="2222222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            audience=AudienceGroup.NON_TECH,
            unsubscribe_token_hash="tokenhash1234567890abcdef1234567890abcdef1234567890abcdef123456",
        )
        sub.refresh_from_db()
        assert sub.categories == []
        assert sub.categories is not None

    def test_invalid_channel_fails(self):
        """Failing-insert test for ck_sub_channel."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AlertSubscriptionFactory(channel="POST")
        assert "ck_sub_channel" in str(excinfo.value)

        # Positive control: valid channel succeeds
        valid = AlertSubscriptionFactory(channel=Channel.SMS)
        assert valid.channel == Channel.SMS

    def test_invalid_status_fails(self):
        """Failing-insert test for ck_sub_status."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AlertSubscriptionFactory(status="SUSPENDED")
        assert "ck_sub_status" in str(excinfo.value)

        # Positive control: valid status succeeds
        valid = AlertSubscriptionFactory(status=SubscriptionStatus.ACTIVE)
        assert valid.status == SubscriptionStatus.ACTIVE

    def test_invalid_audience_fails(self):
        """Failing-insert test for ck_sub_audience."""
        with pytest.raises(IntegrityError) as excinfo:
            with transaction.atomic():
                AlertSubscriptionFactory(audience="KIDS")
        assert "ck_sub_audience" in str(excinfo.value)

        # Positive control: valid audience succeeds
        valid = AlertSubscriptionFactory(audience=AudienceGroup.TEENAGER)
        assert valid.audience == AudienceGroup.TEENAGER


@pytest.mark.django_db
class TestBoundaryPasses:
    def test_boundary_endpoint_max_length(self):
        val = "a" * 242 + "@example.com"
        assert len(val) == 254
        sub = AlertSubscriptionFactory(endpoint=val)
        assert len(sub.endpoint) == 254

    def test_boundary_endpoint_hash_length(self):
        val = "h" * 64
        sub = AlertSubscriptionFactory(endpoint_hash=val)
        assert len(sub.endpoint_hash) == 64

    def test_boundary_unsubscribe_token_hash_length(self):
        val = "u" * 64
        sub = AlertSubscriptionFactory(unsubscribe_token_hash=val)
        assert len(sub.unsubscribe_token_hash) == 64

    def test_boundary_sns_subscription_arn_length(self):
        val = "arn:aws:sns:ap-southeast-1:123456789012:" + "x" * 216
        assert len(val) == 256
        sub = AlertSubscriptionFactory(sns_subscription_arn=val)
        assert len(sub.sns_subscription_arn) == 256


@pytest.mark.django_db
class TestOnDeleteAndPrivacy:
    def test_user_set_null_on_delete(self):
        user = UserFactory()
        sub = AlertSubscriptionFactory(user=user)
        assert sub.user == user

        user.delete()
        sub.refresh_from_db()
        assert sub.user is None

    def test_str_never_exposes_pii(self):
        raw_email = "private_citizen_email@example.com"
        hash_val = "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        sub = AlertSubscriptionFactory(
            channel=Channel.EMAIL,
            endpoint=raw_email,
            endpoint_hash=hash_val,
            audience=AudienceGroup.GENERAL,
        )
        sub_str = str(sub)
        assert raw_email not in sub_str
        assert hash_val not in sub_str
        assert "EMAIL" in sub_str
        assert "GENERAL" in sub_str
