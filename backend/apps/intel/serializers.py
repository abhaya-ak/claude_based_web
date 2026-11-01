from rest_framework import serializers

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
