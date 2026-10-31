---
description: Close a task or phase safely (usage: /finish-phase)
---
1. Run the /verify workflow. Stop if anything fails.
2. If API changed: regenerate backend/openapi.yaml.
3. Update docs/PROGRESS.md: status, what was built, decisions made, commands that work now, known issues.
4. Write a plain-language summary for the owner (max 10 lines).
5. Give a click-through checklist (max 8 steps) the owner can do in the browser to confirm it works.
6. Propose a commit message `phase-N: <what>` and commit only after the owner confirms the click-through.
