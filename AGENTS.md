# AGENTS.md — ScamShield Cloud (read first, every session)

## Project
University cloud project (CT071-3-3-DDAC): scam reporting + lookup + literacy platform.
React SPA + Django REST API + PostgreSQL on AWS (CloudFront, S3, ALB, EC2 Auto Scaling running Docker, RDS Multi-AZ, Lambda, SNS, CloudWatch).

## The owner
The owner does NOT read or write code. Explain in plain, short language. Never ask them to edit code. Give click-through checks instead. Ask at most ONE question at a time, and only when the docs do not answer it.

## Source of truth (highest wins)
1. docs/03a-database-design.md — schema, enums, constraints
2. docs/02-project-architecture.md — stack, security, rules R-*
3. docs/03-backend-build-plan.md — phases, tests, definition of done
4. docs/01-project-overview.md — features, journeys, requirements
5. docs/PROGRESS.md — current state
If docs conflict or are silent: STOP and ask. Never invent endpoints, fields, enums, libraries, AWS services, or behaviour.

## Session protocol
1. START: read docs/PROGRESS.md, then only the doc sections named in the task.
2. PLAN: list files to touch, tests to write, risks, open questions. WAIT for approval.
3. BUILD: smallest change that meets the acceptance criteria. Tests first for business rules.
4. PROVE: run lint + tests + migration check; paste real output. No "should work".
5. REPORT: Done / Not done / How verified / What the owner should click / Risks.
6. FINISH: update docs/PROGRESS.md, commit `phase-N: <what>`.

## Hard bans
- No new dependency, endpoint, column, enum, AWS service not in docs/.
- Never delete, skip, or weaken a test to get green.
- Never hardcode or print secrets; never commit .env, keys, tfstate.
- No destructive command (rm -rf, DB drop/reset, force-push, terraform destroy, aws delete-*, IAM changes) without explicit approval.
- Do not edit docs/ (except PROGRESS.md) or .agents/ unless the task says so.
- Same failure 3 times → stop, summarise attempts and hypotheses, ask.

## Quality bar
Business logic in services/, thin views, explicit permissions, no PII in logs, AWS calls non-blocking and failure-tolerant. Details: .agents/rules/.
