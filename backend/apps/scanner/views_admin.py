from django.db import IntegrityError, transaction
from django.db.models import F
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasRole
from apps.core import audit
from apps.core.exceptions import ConflictError
from apps.core.ip import client_ip_hash
from apps.core.pagination import StandardPagination
from apps.ops.models import AuditEventType
from apps.scanner.models import HeuristicRule, RuleType, ScannerConfig
from apps.scanner.serializers import HeuristicRuleSerializer, ScannerConfigSerializer


class RuleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]
    serializer_class = HeuristicRuleSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = HeuristicRule.objects.all().order_by("rule_type", "pattern", "id")
        rule_type = self.request.query_params.get("rule_type")
        if rule_type:
            if rule_type not in RuleType.values:
                raise serializers.ValidationError({"rule_type": f"Must be one of {RuleType.values}"})
            qs = qs.filter(rule_type=rule_type)

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            if is_active.lower() in ("true", "1"):
                qs = qs.filter(is_active=True)
            elif is_active.lower() in ("false", "0"):
                qs = qs.filter(is_active=False)
            else:
                raise serializers.ValidationError({"is_active": "Must be true or false."})

        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            rule_type = serializer.validated_data["rule_type"]
            pattern = serializer.validated_data["pattern"]

            if HeuristicRule.objects.filter(rule_type=rule_type, pattern=pattern).exists():
                raise ConflictError("A rule with this type and pattern already exists.")

            try:
                rule = serializer.save(created_by=self.request.user)
            except IntegrityError as exc:
                raise ConflictError("A rule with this type and pattern already exists.") from exc

            ScannerConfig.objects.get_or_create(id=1, defaults={"ruleset_version": 1})
            ScannerConfig.objects.filter(id=1).update(
                ruleset_version=F("ruleset_version") + 1,
                updated_by=self.request.user,
            )
            config = ScannerConfig.objects.get(id=1)

            audit.log_event(
                event_type=AuditEventType.RULE_CHANGED,
                actor=self.request.user,
                ip_hash=client_ip_hash(self.request),
                target=("RULE", str(rule.id)),
                metadata={
                    "action": "created",
                    "rule_type": rule.rule_type,
                    "weight": rule.weight,
                    "is_active": rule.is_active,
                    "ruleset_version": config.ruleset_version,
                },
            )


class RuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]
    serializer_class = HeuristicRuleSerializer
    queryset = HeuristicRule.objects.all()

    def perform_update(self, serializer):
        with transaction.atomic():
            try:
                rule = serializer.save()
            except IntegrityError as exc:
                raise ConflictError("A rule with this type and pattern already exists.") from exc

            ScannerConfig.objects.get_or_create(id=1, defaults={"ruleset_version": 1})
            ScannerConfig.objects.filter(id=1).update(
                ruleset_version=F("ruleset_version") + 1,
                updated_by=self.request.user,
            )
            config = ScannerConfig.objects.get(id=1)

            audit.log_event(
                event_type=AuditEventType.RULE_CHANGED,
                actor=self.request.user,
                ip_hash=client_ip_hash(self.request),
                target=("RULE", str(rule.id)),
                metadata={
                    "action": "updated",
                    "rule_type": rule.rule_type,
                    "weight": rule.weight,
                    "is_active": rule.is_active,
                    "ruleset_version": config.ruleset_version,
                },
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            rule_id = instance.id
            rule_type = instance.rule_type
            instance.delete()

            ScannerConfig.objects.get_or_create(id=1, defaults={"ruleset_version": 1})
            ScannerConfig.objects.filter(id=1).update(
                ruleset_version=F("ruleset_version") + 1,
                updated_by=self.request.user,
            )
            config = ScannerConfig.objects.get(id=1)

            audit.log_event(
                event_type=AuditEventType.RULE_CHANGED,
                actor=self.request.user,
                ip_hash=client_ip_hash(self.request),
                target=("RULE", str(rule_id)),
                metadata={
                    "action": "deleted",
                    "rule_type": rule_type,
                    "ruleset_version": config.ruleset_version,
                },
            )


class ScannerConfigView(APIView):
    permission_classes = [IsAuthenticated, HasRole(Role.ADMIN)]
    serializer_class = ScannerConfigSerializer

    def get(self, request):
        config, _ = ScannerConfig.objects.get_or_create(id=1, defaults={"ruleset_version": 1})
        serializer = ScannerConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        with transaction.atomic():
            config, _ = ScannerConfig.objects.select_for_update().get_or_create(
                id=1, defaults={"ruleset_version": 1}
            )
            serializer = ScannerConfigSerializer(config, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save(updated_by=request.user)

            ScannerConfig.objects.filter(id=1).update(ruleset_version=F("ruleset_version") + 1)
            config.refresh_from_db()

            metadata = {"ruleset_version": config.ruleset_version}
            for field in serializer.validated_data:
                metadata[field] = getattr(config, field)

            audit.log_event(
                event_type=AuditEventType.CONFIG_CHANGED,
                actor=request.user,
                ip_hash=client_ip_hash(request),
                target=("CONFIG", "1"),
                metadata=metadata,
            )

        return Response(ScannerConfigSerializer(config).data, status=status.HTTP_200_OK)
