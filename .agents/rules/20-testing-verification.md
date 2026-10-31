---
trigger: always_on
description: Testing and proof requirements
---
# Testing and verification
- Tools: pytest-django, factory_boy, moto (AWS mocks), ruff.
- Commands (from backend/): `ruff check .` ; `pytest -q` ; `python manage.py makemigrations --check --dry-run` ; `DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy`
- Write the failing test FIRST for every rule listed under "Must-have tests" in docs/03-backend-build-plan.md.
- Bug fix = a test that reproduces the bug first, then the fix.
- Never delete, skip, xfail, or loosen a test; never mock the unit under test. If a test seems wrong, explain and ask.
- A task is not done until lint, tests, and migration check pass and the output is pasted.
- Coverage target: 80%+ on services/ and selectors/.
- UI work: start the app, drive it with the browser tool, take a screenshot for each acceptance step.
- Report honestly what was NOT tested.
