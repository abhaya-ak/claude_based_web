from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Role, User


class AdminUserSerializer(serializers.ModelSerializer):
    approved_by = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "role",
            "approval_status",
            "organization",
            "credential_note",
            "rejection_reason",
            "approved_by",
            "approved_at",
            "is_active",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_approved_by(self, obj):
        return str(obj.approved_by_id) if obj.approved_by_id else None


class RejectUserSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, allow_blank=False)

    def validate_reason(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Rejection reason cannot be blank.")
        return val


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)
