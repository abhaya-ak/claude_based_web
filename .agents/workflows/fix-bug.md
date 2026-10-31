---
description: Disciplined bug fixing with a reproducing test (usage: /fix-bug <what you saw>)
---
1. Restate the bug in one sentence and the expected behaviour from the docs.
2. Reproduce it. Write a failing automated test that captures it. Show the failure output.
3. Explain the root cause in plain language (no guessing; point to the exact file and line).
4. Apply the smallest fix. No refactors.
5. Run the new test and the full suite. Paste output.
6. If the same attempt fails 3 times: stop, list 3 hypotheses with evidence for each, and ask the owner.
7. Append a line to docs/PROGRESS.md under Known issues / Fixed.
