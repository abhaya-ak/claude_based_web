---
trigger: glob
globs: backend/**
description: Django/DRF backend conventions for ScamShield
---
# Django backend rules
Layout per app: models.py, serializers.py, views.py, urls.py, permissions.py, services/ (writes), selectors/ (reads), tests/.
- Views: parse input, call service/selector, return response. No business logic, no boto3, no raw SQL.
- Services: business rules; `transaction.atomic()` for multi-row writes; AWS calls only through `core.aws.client()` inside `transaction.on_commit`, wrapped in try/except + log; never fail the user request because of Lambda/SNS/CloudWatch.
- Models: match docs/03a exactly (names, types, constraints, indexes, on_delete). Custom user model `accounts.User`. UUID PKs for public objects. TextChoices + CheckConstraint.
- Serializers: explicit fields (never `__all__`); separate read/write; public serializers must NOT expose raw_value, message_text, reporter, IP, s3_key, internal IDs.
- Permissions: default IsAuthenticated; AllowAny only for endpoints marked public in docs/02 section 6; role checks via HasRole; object-level checks for own resources.
- Queries: select_related/prefetch_related; paginate everything; allow-list ordering and filters; assertNumQueries test for list endpoints.
- Concurrency: F() for counters; select_for_update in verify flow; rely on DB unique constraints for get_or_create.
- Migrations: backward-compatible; never edit an applied migration; never run migrate at container start.
- Errors: use core.errors envelope; never leak stack traces.
- Logging: JSON; never log PII, message text, tokens, phone/email/bank values.
- Config: environment variables via settings only; no hardcoded region, ARNs, URLs.
- Anonymous reports: no reporter link, no raw IP anywhere.
