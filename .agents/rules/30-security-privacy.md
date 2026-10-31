---
trigger: always_on
description: Security and privacy non-negotiables
---
# Security and privacy
- Secrets: only env vars / SSM. Never in code, Dockerfile, logs, screenshots, or chat.
- Auth: access token 15 min in memory only; refresh token HttpOnly Secure SameSite=Lax cookie; rotate + blacklist. Never store tokens in localStorage.
- Every endpoint authenticated by default; public ones are explicit and tested.
- IDOR: every object lookup for a user-owned resource filters by owner or role; test it.
- Uploads: allow-list type by magic bytes, size caps, UUID filenames, private S3, evidence only via 15-minute pre-signed URLs for ANALYST.
- Public responses (lookup, tracking, advisories, guides) never include victim text, raw indicators, reporter, IP, evidence, storage keys.
- Logs/metrics/audit metadata contain no PII. IPs only as salted HMAC.
- Rate limits count from the shared DB, not process memory.
- Internal callback endpoint requires HMAC signature + timestamp (+/-5 min), constant-time compare.
- Use `PUBLIC_BASE_URL` for links in alerts; never `build_absolute_uri`.
- Django admin and DRF browsable API disabled in production.
