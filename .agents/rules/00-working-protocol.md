---
trigger: always_on
description: How the agent must work on every task
---
# Working protocol
1. One task at a time. Do not start the next task without the owner's go-ahead.
2. Plan first (files, tests, risks, questions). Wait for approval before editing.
3. Smallest change that satisfies the acceptance criteria. No drive-by refactors, renames, or "improvements".
4. Anything not in docs/ (dependency, endpoint, column, enum, AWS service) needs approval with a one-line reason.
5. Doc ambiguous or contradicts code: stop, quote both, ask ONE question.
6. Prove, don't claim: run commands, paste real output.
7. End every task with: Done / Not done / How verified / What to click / Risks.
8. Same failure 3 times: stop and report hypotheses. No random retry loops.
9. Never modify docs/ (except PROGRESS.md), .agents/, .github/ (unless task is CI).
10. Destructive or costly actions need explicit approval first (delete, reset, force-push, terraform apply/destroy, aws create/delete, IAM).
11. Commit after each green task: `phase-N: <what>`. Never commit secrets.
12. Update docs/PROGRESS.md at the end of every task.
13. If a task is too big (more than ~8 files or 1 feature slice), split it and propose the split.
