from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import Role, User


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role", "approval_status")
        read_only_fields = fields


class CitizenRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    full_name = serializers.CharField(max_length=150)
    role = serializers.CharField(required=False, write_only=True)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_password(self, value):
        validate_password(value)
        return value


class StaffRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    full_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=[Role.ANALYST, Role.EDUCATOR])
    organization = serializers.CharField(max_length=200, allow_blank=False)
    credential_note = serializers.CharField(max_length=1000, allow_blank=False)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_organization(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Organization cannot be blank.")
        return val

    def validate_credential_note(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Credential note cannot be blank.")
        return val


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        return value.strip().lower()
