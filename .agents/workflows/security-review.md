---
description: Review the current diff against the project's security and privacy rules (usage: /security-review)
---
1. List changed files (git diff against main).
2. Check each against .agents/rules/30-security-privacy.md and the rulebook R-A..R-F in docs/02-project-architecture.md section 16.
3. Specifically verify: public serializers expose no forbidden fields; every new endpoint has explicit permissions and a role test; IDOR checks; uploads validated; no PII in logs; AWS calls have timeouts and run after commit; no secrets in code.
4. Output a table: rule | status (ok/violation/not applicable) | file:line | fix.
5. Do not change code; report only.
