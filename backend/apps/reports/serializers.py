import json
from decimal import Decimal

from rest_framework import serializers

from apps.reports.constants import (
    ALLOWED_COUNTRY_CODES,
    ALLOWED_CURRENCIES,
    MAX_EVIDENCE_FILE_SIZE,
    MAX_EVIDENCE_FILES,
    MAX_FINANCIAL_LOSS,
    MAX_MESSAGE_LENGTH,
    MAX_SUBMITTED_INDICATORS,
    MIN_FINANCIAL_LOSS,
    MIN_MESSAGE_LENGTH,
    MIN_SUBMITTED_INDICATORS,
)
from apps.reports.evidence import (
    EvidenceValidationError,
    validate_and_process_evidence_file,
)
from apps.reports.models import (
    IndicatorType,
    PaymentMethod,
    Platform,
    ScamCategory,
    ScamReport,
)
from apps.reports.normalizers import NormalizationError
from apps.reports.validators import validate_admin_area, validate_financial_loss


class StepSerializer(serializers.Serializer):
    marker = serializers.CharField(required=False, allow_null=True)
    title = serializers.CharField(max_length=150)
    detail = serializers.CharField()


class PlaybookSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    steps = StepSerializer(many=True)
    hotlines = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )


class ReportOptionsResponseSerializer(serializers.Serializer):
    countries = serializers.ListField(child=serializers.DictField())
    currencies = serializers.ListField(child=serializers.CharField())
    categories = serializers.ListField(child=serializers.DictField())
    platforms = serializers.ListField(child=serializers.DictField())
    payment_methods = serializers.ListField(child=serializers.DictField())
    indicator_types = serializers.ListField(child=serializers.DictField())
    admin_areas = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))


class ReportIndicatorItemSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=IndicatorType.choices)
    value = serializers.CharField(max_length=512)


class ReportCreateRequestSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=ScamCategory.choices)
    platform = serializers.ChoiceField(choices=Platform.choices)
    message_text = serializers.CharField(
        min_length=MIN_MESSAGE_LENGTH,
        max_length=MAX_MESSAGE_LENGTH,
        trim_whitespace=True,
    )
    country_code = serializers.ChoiceField(choices=sorted(list(ALLOWED_COUNTRY_CODES)))
    currency = serializers.ChoiceField(choices=sorted(list(ALLOWED_CURRENCIES)))
    financial_loss = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        min_value=MIN_FINANCIAL_LOSS,
        max_value=MAX_FINANCIAL_LOSS,
    )
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        default=PaymentMethod.NONE,
    )
    admin_area = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    incident_date = serializers.DateField(required=False, allow_null=True)
    anonymous = serializers.BooleanField(default=False)
    indicators = serializers.CharField(
        help_text="JSON-encoded array of indicator objects: [{'type': '...', 'value': '...'}]"
    )

    def validate_indicators(self, value):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception as exc:
                raise serializers.ValidationError(
                    f"Invalid JSON format for indicators: {exc}"
                ) from exc
        elif isinstance(value, list):
            parsed = value
        else:
            raise serializers.ValidationError(
                "Indicators must be a JSON array of indicator objects."
            )

        if not isinstance(parsed, list):
            raise serializers.ValidationError("Indicators must be a JSON array.")

        if len(parsed) < MIN_SUBMITTED_INDICATORS:
            raise serializers.ValidationError(
                f"At least {MIN_SUBMITTED_INDICATORS} indicator is required."
            )
        if len(parsed) > MAX_SUBMITTED_INDICATORS:
            raise serializers.ValidationError(
                f"At most {MAX_SUBMITTED_INDICATORS} indicators may be submitted."
            )

        item_serializer = ReportIndicatorItemSerializer(data=parsed, many=True)
        if not item_serializer.is_valid():
            raise serializers.ValidationError(item_serializer.errors)

        return item_serializer.validated_data

    def validate(self, attrs):
        country_code = attrs.get("country_code")
        admin_area = attrs.get("admin_area")
        try:
            validate_admin_area(country_code, admin_area)
        except NormalizationError as exc:
            raise serializers.ValidationError({"admin_area": [str(exc.message)]}) from exc

        payment_method = attrs.get("payment_method", PaymentMethod.NONE)
        financial_loss = attrs.get("financial_loss", Decimal("0.00"))
        try:
            attrs["financial_loss"] = validate_financial_loss(financial_loss, payment_method)
        except NormalizationError as exc:
            raise serializers.ValidationError({"financial_loss": [str(exc.message)]}) from exc

        return attrs


def validate_evidence_files(file_list):
    """
    Validates uploaded evidence files against limits and sniffing signatures.
    """
    if len(file_list) > MAX_EVIDENCE_FILES:
        raise serializers.ValidationError(
            {"evidence": [f"At most {MAX_EVIDENCE_FILES} evidence files are permitted."]}
        )

    file_bytes_list = []
    for idx, f in enumerate(file_list):
        if f.size > MAX_EVIDENCE_FILE_SIZE:
            raise serializers.ValidationError(
                {"evidence": [f"File {idx + 1} exceeds maximum size of 5 MB."]}
            )
        raw_bytes = f.read()
        try:
            # Validate through pure evidence validator
            validate_and_process_evidence_file(raw_bytes)
            file_bytes_list.append(raw_bytes)
        except EvidenceValidationError as exc:
            raise serializers.ValidationError(
                {"evidence": [f"File {idx + 1} failed validation: {exc.message}"]}
            ) from exc

    return file_bytes_list


class ReportCreateResponseSerializer(serializers.Serializer):
    reference_code = serializers.CharField(max_length=24)
    status = serializers.CharField(max_length=10)
    access_key = serializers.CharField(max_length=64, required=False, allow_null=True)
    playbook = PlaybookSerializer()


class ReportTrackRequestSerializer(serializers.Serializer):
    reference_code = serializers.CharField(max_length=24, required=True)
    access_key = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True
    )


class ReportTrackResponseSerializer(serializers.Serializer):
    reference_code = serializers.CharField(max_length=24)
    status = serializers.CharField(max_length=10)
    category = serializers.CharField(max_length=20)
    platform = serializers.CharField(max_length=12)
    financial_loss = serializers.CharField()
    currency = serializers.CharField(max_length=3)
    created_at = serializers.DateTimeField()
    playbook = PlaybookSerializer()


class MyReportItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScamReport
        fields = [
            "reference_code",
            "category",
            "platform",
            "status",
            "financial_loss",
            "currency",
            "created_at",
        ]
