# Vibe-Coding Playbook — building ScamShield Cloud with Antigravity (for a non-coder)

## 0. Honest expectations

- **"Zero bugs" can't be promised by anyone, human or AI.** What you can get is: *no known bugs, proven by automated tests, a CI gate, your own click-through checks, and monitoring.* This playbook builds that.
- **Deploy target:** I'm assuming "deploy on claude" means **AWS** (the project brief requires AWS). Claude (in chat) can't log into your AWS account. The Antigravity agent runs the commands in *your* terminal with *your* credentials, after you approve each step.
- Antigravity features move fast. Folder names and settings below match current docs (`.agents/rules`, `.agents/workflows`, `.agents/skills`, `AGENTS.md`). If something looks different in your version, check **Settings → Customizations** and tell the agent to adapt the file locations — don't change the method.

## 1. Mental model

You are the **product owner + tester**. The agent is a fast, over-confident junior developer with no memory between chats. It goes wrong when instructions are vague, tasks are huge, or nothing forces it to prove its work. So you control four things:

| Pillar | What you do |
|---|---|
| **Specs** | The 4 docs in `docs/` are the only truth. Agent may not invent. |
| **Rules** | `AGENTS.md` + `.agents/rules/*` are always loaded; they forbid guessing and enforce quality. |
| **Small steps + proof** | One task per chat. Every task ends with real test output + a click-through you perform. |
| **Memory** | `docs/PROGRESS.md` is the agent's memory. Every new chat starts by reading it. |

## 2. What's in this kit

```
your-repo/
├── AGENTS.md                         # constitution (auto-read by Antigravity)
├── .agents/
│   ├── rules/                        # standing rules
│   │   ├── 00-working-protocol.md    # always on
│   │   ├── 10-backend-django.md      # applies to backend/**
│   │   ├── 20-testing-verification.md# always on
│   │   ├── 30-security-privacy.md    # always on
│   │   ├── 40-infra-deploy.md        # infra/**, Dockerfile, .github/**
│   │   └── 50-frontend-react.md      # frontend/**
│   └── workflows/                    # your "buttons": type /name in the agent box
│       ├── start-phase.md            # /start-phase 4   -> plan only, no edits
│       ├── verify.md                 # /verify          -> run all gates, report
│       ├── fix-bug.md                # /fix-bug <issue> -> failing test first
│       ├── security-review.md        # /security-review -> audit the diff
│       └── finish-phase.md           # /finish-phase    -> verify + update memory + checklist
└── docs/
    ├── 01-project-overview.md  02-project-architecture.md
    ├── 03-backend-build-plan.md  03a-database-design.md
    └── PROGRESS.md                   # agent memory (it updates this)
```

Rule files carry `trigger:` front-matter (`always_on` / `glob`). If your version ignores it, open **Customizations → Rules** and set each rule's activation by hand: 00, 20, 30 = Always On; 10, 40, 50 = Glob (patterns are in each file). Keep every rule/workflow file small (Antigravity limits file size; these are all far below it).

## 3. Day-0 setup (do once)

1. Install Antigravity, Git, Docker Desktop, Node.js, Python 3.12, AWS CLI. (Ask the agent: *"Check which of these are installed on my machine and give me exact install links for what's missing. Don't install anything."*)
2. Create a GitHub repo `scamshield`. Clone it. Copy the **contents of this kit** into the repo root (include the hidden `.agents` folder). Commit: `chore: add agent kit and docs`.
3. In GitHub: protect `main` (require pull request + passing checks). The agent works on branches, never on `main`.
4. Open the repo as the workspace in Antigravity. Settings to choose:
   - **Planning mode** (agent writes a plan before coding) — not "fast" mode, for anything that touches data, auth, or AWS.
   - **Terminal commands: ask for approval** (don't auto-run). Allow-list only harmless ones (`ls`, `pytest`, `ruff`, `git status/diff`).
   - **Review policy: request review** for changes (you approve plans/diffs).
   - Browser tool: allow only `localhost` and your CloudFront URL.
5. **Comprehension check** (this exposes hallucination early). New chat, paste:

```
Read AGENTS.md, everything in .agents/rules, and everything in docs/.
Do NOT write any code or create files.
Reply with:
1) The project in 10 lines, in your own words.
2) The rules you will follow (bullet list, short).
3) Contradictions or gaps between the four docs (quote each, with file + section).
4) The 5 biggest technical risks you see.
5) The first 3 things you would do, in order.
Then stop and wait.
```

   If the summary is wrong or generic, fix the docs (ask the agent to propose edits; you approve) before any coding. Resolve each contradiction with a written decision in `docs/PROGRESS.md → Decisions`.

## 4. The loop (every single task)

```
New chat → /start-phase N → read the Plan → "Approved, do task 1 only" →
agent builds + shows proof → /verify → (risky phases) /security-review →
YOU click through the checklist → /finish-phase → commit → next task
```

1. **New chat per task.** Long chats rot: the agent forgets rules and starts improvising. `PROGRESS.md` carries the memory.
2. **Plan gate.** Read the Plan artifact. Approve only if: ≤ 8 tasks, files named, tests listed first, nothing outside the docs. If it adds libraries/endpoints/columns: reply *"That's not in the docs. Remove it or justify in one line."*
3. **Build one task** with the template in §5.
4. **Proof.** You want real command output (tests passing), not "done". For UI: screenshots/browser recording artifacts.
5. **Second opinion.** For auth, payments-like logic, uploads, AWS: run `/security-review`. If the model picker offers another model, switch to it for the review — different models catch different mistakes.
6. **Your click-through.** The agent gives you ≤ 8 steps. If you can't complete them, it isn't done.
7. **Commit** after each green task. Never stack unverified work.

## 5. How to give detailed instructions (copy this template)

```
TASK: <one sentence>
READ FIRST: @docs/03a-database-design.md (section 4.2), @docs/03-backend-build-plan.md (Phase 4)
SCOPE (you may touch only): backend/apps/reports/**
OUT OF SCOPE: everything else. No new dependencies. No doc edits.
ACCEPTANCE (all must be true):
 1) <observable behaviour>
 2) <observable behaviour>
 3) <failure case behaviour>
PROVE IT: run ruff, pytest -q, makemigrations --check; paste outputs.
          Then give me a click-through (max 8 steps) to verify in the browser/Postman.
STOP AND ASK IF: the docs are unclear, a test needs changing, you need a new dependency, or the same error happens 3 times.
```

Why it works: it pins **what to read**, **where to write**, **what "done" means**, **how to prove it**, and **when to stop**.

**Good vs bad**
- Bad: *"Build the report feature."* (huge, undefined, agent invents.)
- Good: *"Implement the phone and URL normalisers in `reports/normalizers.py` exactly per the table in Phase 4, with ≥ 10 unit tests per type including +60 and +977 numbers. Nothing else."*

## 6. Anti-hallucination tactics

| Tactic | How |
|---|---|
| Attach only needed docs | Use `@docs/...` for the section you need; don't attach everything every time |
| Make it quote the spec | *"Before coding, quote the exact table row/rule you are implementing."* |
| Tests before code | Workflow and rules demand failing tests first for business rules |
| Ban invention | AGENTS.md hard bans; keep reminding: *"Not in docs = not allowed."* |
| Ask for evidence | *"Show the command and its output."* — never accept "I verified" |
| Small diffs | If the diff is > ~10 files, reject and split |
| Fresh chat on drift | If it contradicts a rule or forgets a decision, start a new chat |
| Pin decisions | Write decisions in `PROGRESS.md → Decisions` so they survive |

**Red flags (stop immediately):** a library or endpoint you've never seen in the docs · "all tests pass" without output · changed or deleted tests · `TODO`/placeholder/mock data in real code paths · giant diffs · touching unrelated files · AWS resource "created" with no command output · secrets pasted anywhere.

## 7. When the agent is stuck or looping

1. Say: *"Stop. Don't change anything. Explain what you tried, what you observed, and give 3 hypotheses with evidence for each."*
2. Pick one hypothesis; ask for a **test or log that would confirm it** before any fix.
3. Still stuck after one more cycle → `git restore .` (or `git reset --hard` to the last good commit), start a **new chat**, shrink the task, and paste only: the task, the exact error text, and the last good behaviour.
4. Still stuck → ask in your team chat or here with: the error, the command, the file name. Don't keep paying for random retries.

## 8. Phase prompts (what to type)

Pattern for **every** phase: `/start-phase N` → read plan → `Approved. Do task 1 only. Tests first. Stop after you prove it.` → `/verify` → `/finish-phase`.

| Phase | First message in a new chat | Extra instruction to add |
|---|---|---|
| 1B Models | `/start-phase 1B` | *"One app per task. Models must match 03a exactly. Add a failing-insert test for every CHECK/UNIQUE."* |
| 2 Scaffold | `/start-phase 2` | *"Prove `docker compose up` gives a working /api/v1/health/ready/."* |
| 3 Auth | `/start-phase 3` | *"Include the role × endpoint matrix test and refresh-token rotation test."* Then `/security-review`. |
| **M0 Walking skeleton** | see §9 | Deploy a "hello" stack to AWS **now**, before features |
| 4 Reports | `/start-phase 4` | *"Normalisers first (pure functions + tests), then service, then endpoints."* |
| 5 Scanner | `/start-phase 5` | *"Lambda scoring function first with the full test table; callback after."* |
| 6 Triage | `/start-phase 6` | *"Include the concurrent verify test."* Then `/security-review`. |
| 7 Lookup | `/start-phase 7` | *"Add a test that proves forbidden fields never appear in the response."* |
| 8 Analytics | `/start-phase 8` | |
| 9–10 Literacy | `/start-phase 9`, `/start-phase 10` | *"Prove correct answers never appear before answering."* |
| 11 Telemetry | `/start-phase 11` | *"Metric emit must never raise, test it with AWS failing."* |
| 12 Hardening | `/start-phase 12` | Run `/security-review` on the whole repo, then the load test |
| 13 Deploy | see §9 | |
| Frontend | **Not yet** — ask for `docs/04-frontend-plan.md` first | Don't let the agent invent screens |

## 9. Deployment without coding (and why to start early)

**Recommendation (changes the original order):** after Phase 3, deploy a **walking skeleton** — empty Django with `/health/`, React "Hello", RDS, ALB, ASG, CloudFront — to AWS (milestone **M0**). Deployment problems (permissions, networking, health checks, Learner Lab limits) are the #1 project killer; finding them in week 8 beats finding them in week 13. Every later phase then deploys through the same pipeline.

**Before the agent touches AWS**
1. Create/confirm your AWS access. Use SSO or a limited IAM user (never root). If you use AWS Academy Learner Lab, credentials expire; paste them into `~/.aws/credentials` **yourself** — never into chat.
2. Ask: *"Verify my AWS login with `aws sts get-caller-identity` and show me the account ID and region only."*
3. **First infra task is always the Budgets alarm.**

**Deploy prompt (M0 / Phase 13)**

```
TASK: Provision and deploy the walking skeleton to AWS exactly as docs/02-project-architecture.md sections 2, 9, 10, 13, 14 describe.
READ FIRST: @docs/02-project-architecture.md @.agents/rules/40-infra-deploy.md
METHOD: Write Terraform in infra/ (or, if Terraform is blocked in my account, a step-by-step runbook in docs/runbook.md). Work in small stacks: network -> database -> storage -> compute -> edge.
RULES: Show `terraform plan` and a monthly cost estimate for each stack and WAIT for my approval before every apply. Tag all resources. No public DB. No secrets in files.
PROVE IT: after each stack, run read-only AWS CLI commands that show the resources exist; at the end, open the CloudFront URL in the browser tool and show /api/v1/health/ready/ returning OK.
STOP AND ASK IF: any permission error, any cost above my estimate, or any step not covered by the docs.
```

**After deploy, prove it** (capture screenshots for your report): ALB healthy targets (2), ASG in 2 AZs, RDS Multi-AZ, CloudWatch dashboard, a Lambda log line, an SNS email arriving. Do the **kill-an-instance** test and confirm the site stays up.

**Cost control:** when not testing, ask the agent: *"Give me a command to scale the ASG to 0 and stop RDS (or tell me what can't be stopped)."* and *"Give me the teardown command."* NAT gateways and ALBs bill by the hour.

## 10. Your click-through tests (you don't need code)

Create demo users via the seed command (agent provides). Then, per role:

- **Citizen:** submit an anonymous report with 2 screenshots → get reference + access key → check status with both → try wrong key (must fail the same way as unknown reference) → submit 6 times quickly from one browser (6th must be blocked).
- **Lookup:** paste a seeded scam number → RED; paste a random number → GREEN; subscribe with your email → confirm email arrives.
- **Analyst:** log in → queue sorted by risk → open report → evidence image loads → verify → lookup now shows RED with new count → publish advisory → email arrives.
- **Educator:** create a guide with a PDF → publish → appears in public hub filtered for Elderly with large-font mode → create 5+ scenarios → play the simulator as a citizen → score + recommended guides.
- **Admin:** approve a new analyst → add a keyword rule → submit a report containing it → higher risk score → telemetry charts show data → audit log shows each action.
- **Security spot checks:** open the evidence URL after 16 minutes (must fail); log in as a citizen and try an analyst URL (must be blocked); view page source of lookup result (no victim text).

## 11. Quality gates (what "works" means)

A task/phase is **done** only when all five are true:
1. `/verify` passes (lint, tests, migration check, deploy check).
2. Required tests from the phase exist and are meaningful (you can ask: *"List the tests you wrote and what rule each proves."*).
3. `/security-review` shows no violations (risky phases).
4. **You** completed the click-through.
5. `PROGRESS.md` updated and commit made; CI is green on the PR.

## 12. Daily routine

1. Open `docs/PROGRESS.md` → pick the next task.
2. New chat → `/start-phase N`.
3. Work the loop in §4. One task, one commit.
4. End of day: `/finish-phase`, push the branch, open a PR, wait for CI.
5. Weekly: paste `PROGRESS.md` into your team chat; run the load test after Phase 12.

## 13. Team rules (4 students, 4 agents)

- Each student works on their own phases and **their own app folders** (see the workload matrix). Never ask the agent to edit another student's app; ask them.
- Shared files (`core/`, settings, infra, docs): only S4 changes them, via PR; others request changes in the issue board.
- Contracts in `docs/` (03 → Phase 1A table) are frozen. Changing one needs all four to agree and a `Decisions` entry.
- Merge small PRs often to avoid conflicts; rebase daily.
