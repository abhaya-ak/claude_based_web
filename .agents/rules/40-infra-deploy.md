---
trigger: glob
globs: infra/**, **/Dockerfile, docker-compose*.yml, .github/**
description: AWS, Docker and CI safety rules
---
# Infra, Docker, CI
- Credentials: use an SSO/named profile (AWS_PROFILE). Never root credentials. Never write keys into files or chat.
- Before any `terraform apply` / `aws ... create|delete|update`: show the plan, list resources and monthly cost estimate, WAIT for approval.
- First infra task is always an AWS Budgets alarm. Tag every resource: Project=scamshield, Env, Owner.
- Region is a variable (default from docs); never hardcode.
- Network: RDS private, not public; no 0.0.0.0/0 on ports 22 or 5432; app SG only from ALB SG; DB SG only from app SG; SSM Session Manager instead of SSH.
- S3: Block Public Access ON, ACLs off, encryption on; media via CloudFront OAC only.
- ALB accepts only requests carrying the secret origin header; health check path /api/v1/health/ must pass without host validation.
- Docker: multi-stage, python:3.12-slim, non-root, no secrets/.env/.git in image, HEALTHCHECK, gunicorn entrypoint, NO migrations in entrypoint, tag = git SHA (never `latest`).
- Deploy order: migrate once (SSM Run Command) -> update IMAGE_TAG -> instance refresh -> smoke test -> SPA sync. Rollback = previous IMAGE_TAG.
- CI must be green to deploy: ruff, tests, migration check, check --deploy, openapi diff, pip-audit.
- Every infra change is committed as code (or runbook step in docs/runbook.md). No undocumented console clicks.
- After building, list every resource created and provide a teardown command.
