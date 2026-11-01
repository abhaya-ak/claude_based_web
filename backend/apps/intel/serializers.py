from rest_framework import serializers

from apps.intel.models import VerifiedIndicator
from apps.reports.models import ReportEvidence, ReportIndicator, ScamReport
from apps.scanner.models import ScanResult


class QueueReportSerializer(serializers.ModelSerializer):
    cluster_size = serializers.IntegerField(read_only=True)

    class Meta:
        model = ScamReport
        fields = [
            "id",
            "reference_code",
            "category",
            "platform",
            "financial_loss",
            "currency",
            "incident_date",
            "status",
            "risk_score",
            "is_high_priority",
            "scan_status",
            "cluster_size",
            "created_at",
        ]
        read_only_fields = fields


class IndicatorDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportIndicator
        fields = [
            "id",
            "type",
            "raw_value",
            "normalized_value",
            "display_value",
            "verified_indicator",
            "created_at",
        ]
        read_only_fields = fields


class EvidenceMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportEvidence
        fields = [
            "id",
            "content_type",
            "size_bytes",
            "sha256",
            "created_at",
        ]
        read_only_fields = fields


class ScanResultDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanResult
        fields = [
            "ruleset_version",
            "risk_score",
            "is_high_priority",
            "breakdown",
            "scanned_at",
        ]
        read_only_fields = fields


class ReportDetailSerializer(serializers.ModelSerializer):
    cluster_size = serializers.IntegerField(read_only=True)
    indicators = IndicatorDetailSerializer(many=True, read_only=True)
    evidence_files = EvidenceMetadataSerializer(source="evidence", many=True, read_only=True)
    scan_result = ScanResultDetailSerializer(read_only=True)
    reviewed_by = serializers.SlugRelatedField(slug_field="email", read_only=True)

    class Meta:
        model = ScamReport
        fields = [
            "id",
            "reference_code",
            "status",
            "category",
            "platform",
            "financial_loss",
            "currency",
            "payment_method",
            "country_code",
            "admin_area",
            "incident_date",
            "message_text",
            "risk_score",
            "is_high_priority",
            "scan_status",
            "cluster_size",
            "indicators",
            "evidence_files",
            "scan_result",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EvidencePresignedResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    mime_type = serializers.CharField()
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField()
    download_url = serializers.CharField()
    expires_in = serializers.IntegerField(default=900)


class RejectReportRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        min_length=1,
        max_length=500,
    )

    def validate_reason(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Reason cannot be blank.")
        return val


class RejectReportResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    reference_code = serializers.CharField()


class VerifiedIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerifiedIndicator
        fields = [
            "id",
            "type",
            "normalized_value",
            "display_value",
            "primary_category",
            "threat_level",
            "total_report_count",
            "first_seen_at",
            "last_seen_at",
            "status",
            "public_note",
            "verified_by_id",
            "verified_at",
            "revoked_by_id",
            "revoked_at",
            "revoke_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class VerifyReportRequestSerializer(serializers.Serializer):
    report_indicator_id = serializers.IntegerField(required=True)
    public_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default="",
    )


class VerifyReportResponseSerializer(serializers.Serializer):
    verified_indicator = VerifiedIndicatorSerializer()
    resolved_report_ids = serializers.ListField(child=serializers.CharField())
    cluster_size = serializers.IntegerField()
    threat_level = serializers.CharField()


class CurateIndicatorRequestSerializer(serializers.Serializer):
    public_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default="",
    )

    def validate(self, attrs):
        unknown_fields = set(self.initial_data.keys()) - {"public_note"}
        if unknown_fields:
            raise serializers.ValidationError(
                {field: ["This field is read-only."] for field in unknown_fields}
            )
        return attrs


class RevokeIndicatorRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        min_length=1,
        max_length=300,
    )

    def validate_reason(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Reason cannot be blank.")
        return val
