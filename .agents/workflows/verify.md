---
description: Run all quality gates and report pass/fail with real output (usage: /verify)
---
1. From backend/: run `ruff check .`, `pytest -q`, `python manage.py makemigrations --check --dry-run`, and `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy`.
2. If frontend/ exists: run its lint, typecheck, and tests.
3. Print a table: gate | pass/fail | key output.
4. If anything failed, explain the cause in plain language and propose the smallest fix. Do not fix until the owner approves.
5. Never skip a gate; say explicitly if a gate could not run and why.
