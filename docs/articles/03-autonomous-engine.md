---
title: "The Autonomous Engine — Loops, CI/CD, ARQ + Swarms, Observability"
slug: 03-autonomous-engine
series: How BitSafe Runs on Notion
part: 3
published: 2026-05-14
audience: [App Developers, Trading Firms, Investors]
---

# The Autonomous Engine — Loops, CI/CD, ARQ + Swarms, Observability

This is Part 3 of BitSafe's NanoClaw case study series. Part 1 covered the company-wide AI assistant pattern. Part 2 covered architecture. Part 3 covers the part most readers ask about first: how the system runs *itself* — without an operator hitting "go" in the morning.

## NanoClaw vs Notion AI

Most readers arrive with the same question: how is this different from Notion AI? The honest answer is that they solve different problems, and we use both.

| | NanoClaw | Notion AI |
|---|---|---|
| Surface | Slack, Telegram, calendar, email, X — wherever you work | Inside Notion only |
| Activation | Proactive (scheduled tasks, alerts, dashboards) + reactive | Reactive only |
| Memory | Persistent across sessions, file-based | Per-conversation only |
| Personas | Multiple named bots (Naval, Noob Saibot, legalbot, hrbot) | Single voice |
| Sub-agent orchestration | Fan-out swarms, bot-to-bot via MCP | No |
| Data sources | 20+ caches (Slack, Notion, GDrive, Canton, Fathom...) | Notion content only |
| Autonomy | Runs ops loops, ships own code, self-heals | Conversation-bound |

> Notion AI helps you write inside Notion. NanoClaw is the company's operating system.

The dividing line is not "which one is smarter." It is what each is allowed to do. Notion AI is a smart cursor inside a document. NanoClaw is a process supervisor with hands on every system the company uses — Slack channels, Notion pages, the Canton ledger, the calendar, the deploy pipeline. The article you are reading was drafted by NanoClaw, reviewed in Notion (where Notion AI can help polish prose), and published back to a public URL by NanoClaw's tooling.

The thesis of this article is that the leverage of a company-wide AI is not in the model — it is in the loops the model runs inside. The rest of this piece is a tour of those loops.

## The operating loops

Five loops keep the company moving when nobody is at a keyboard. Each is a few lines of cron, a script, and a state file. None of them is special; the leverage is that they all run together, all the time, and pass work to each other.

**The host-session loop runs every 30 minutes.** `*/30 * * * * root bash /root/nanoclaw/scripts/claude-host-session.sh` fires under a flock at `/var/lock/nanoclaw-host-session.lock`, so overlapping ticks queue rather than collide. Each tick does four things in order: drains the admin inbox at `data/ipc/admin-inbox/req-*.json` (where container agents file requests that need root), runs the goals-vs-ARQ gap scan, picks up the highest-priority admin task from the Notion Tasks DB, and dumps short-term memory back to the persistent memory files. The loop runs `claude --print` inside a `systemd-run` transient scope (`MemoryMax=8G`, `MemorySwapMax=0`, `MemoryHigh=6G`) so a runaway prompt dies in its own scope instead of taking the box down. A sibling cron checks the admin inbox every minute and triggers the same script if a new request lands, so the worst-case latency for an inbox item is one minute, not thirty.

**The ARQ dispatcher runs every 15 minutes during business hours and every hour overnight.** `research-queue-dispatch.py --apply --min-priority P2 --include-surface-actions` reads the Active Research Queue (a Notion database with priority and status), enforces a daily cap of 10 dispatches, and spawns sub-agents for the eligible rows. P3 work has its own slower cadence (every 30 minutes during business hours) so it does not starve P1/P2. The dispatcher writes findings child pages back into Notion and auto-flips parent rows to `Findings ready` when a child page is detected (a 2026-05-13 pre-dispatch guard, after one ARQ row accumulated 26 duplicate findings pages because the dispatcher kept re-picking a row whose status was stuck at "In investigation"). The dispatcher is intentionally separate from the work; it is the planner, not the worker.

**The daily monitor-investigator publishes a dashboard at 09:00 UTC.** A scheduled task generated from `src/monitor.ts` posts a 15-section health report to `#ai-projects-nanoclaw-admin`: cron drift, container counts, scheduled-task staleness, Anthropic spend, security audit status, backup checkpoint age, dead-man heartbeat, and the rest. Some sections auto-remediate before posting — root-owned cache DBs get chowned back to `nanoclaw`, stale lock files get reaped — and Aki is pinged only on judgment calls (a sync that has been silent for three days, a daily spend that just crossed 2× the trailing-7d average, a cron that has not run in 6 hours). The output is structured: every check returns ok / warn / fail with the next-step command inlined, so reading the dashboard takes ~30 seconds.

**The skill reconciler runs hourly.** `/etc/cron.d/skills-sync` fires `scripts/sync-skills-from-notion.py` every hour at :00. The script reads the Notion Skills DB, mirrors each row to disk at three paths (`/root/nanoclaw-skills/<name>/SKILL.md`, `container/skills/<name>/SKILL.md`, `marketing-ai-system/design_system/skills/<name>/SKILL.md`), and parses the frontmatter of each `SKILL.md` for a `scheduled_tasks:` block. Any tasks declared in frontmatter that are not yet present in `store/messages.db` get inserted; tasks that have been removed from frontmatter get marked inactive. The reconciler is the reason a new skill ships with its scheduled cron declaratively in one place — author the SKILL.md row in Notion, and within the hour the on-disk copies update and the schedule is live.

**The dead-man's switch runs every 5 minutes from outside the host.** External uptime monitor watches `https://nanoclaw.bitsafe.finance/api/health` every 5 minutes and pages the admin channel on outage. The reason this is external — UptimeRobot, not an on-host cron — is that every on-host monitor would die simultaneously in a kernel panic or networking failure. If NanoClaw goes silent for >5 minutes, a separate piece of infrastructure tells the team. RECOVERED on resume.

The thing none of these loops do is wait. The dispatcher does not block; it queues. The host-session does not poll; it acts on what is in front of it and exits. The monitor does not loop forever; it runs once per scheduled tick and writes its findings. This matters because the failure mode of an autonomous system is a stuck process — a daemon that thinks it is doing something but is not. Short-lived ticks with state files are easier to reason about than long-running daemons, and they make the system trivial to restart: kill the cron, the next tick picks up where the last one left off.

## The ship-itself loop (CI/CD)

The most consequential loop is the one that ships its own code.

**Dev pipeline.** A push to any `feat/*` or `fix/*` branch triggers `dev-deploy.yml` on GitHub Actions. The workflow builds the container, deploys to the dev VM (`nanoclaw-dev`, `34.29.73.19`, port 8847), and runs a 30-minute smoke watch. The `auto-promote-listener.py` daemon polls the dev VM's health endpoint and, if the watch passes clean, merges the branch to `main` automatically. Prod (`port 8848`) restarts shortly after — `pending-restart.sh` runs every 5 minutes, waits for 0 active container agents, and obeys a 30-minute rate-limit gate to prevent thrash. The whole loop is hands-off: an agent pushes a feature branch, and the code lands on main without anyone clicking merge.

**Hotfix lane.** Any commit message containing `[hotfix]` activates the fast lane. `auto-promote-listener.py` shortens the smoke watch from 30 minutes to 5, writes `data/restart-pending-hotfix` instead of `data/restart-pending`, and `pending-restart.sh` skips its 30-minute rate-limit gate (it still waits for 0 active agents, unless `NANOCLAW_HOTFIX_FORCE_RESTART=1` overrides). Lead time for a typo fix drops from ~36 minutes to ~11. The `[hotfix]` tag is engineer judgment, not a default — it is for fixes that matter now, not cosmetic changes.

**Pre-commit hooks.** Three guards run on every commit. The first is prettier — staged `.ts` files are auto-formatted and re-staged, so a format issue never reaches CI. The second is the encrypted-DB audit — a guard that refuses to commit a SQLite cache that should be encrypted but is not. The third is a worktree-mass-deletion guard that aborts the commit if `git diff --cached --stat` shows >20 deleted files or >2000 net lines removed. The third guard exists because on 2026-05-08, a `git add .` in a stale-baseline worktree wiped 83 files / 6400 lines from a branch that was 90 commits ahead. The hook now blocks that pattern; intentional mass deletions go through `ALLOW_MASS_DELETE=1 git commit`.

**Build cache and rollback.** `npm run build` auto-snapshots `dist/` and sets `data/restart-pending`. `./container/build.sh` auto-tags with release timestamps so an agent can `docker run nanoclaw-agent:2026-05-13T11:51:36Z` to reproduce a specific dispatch. These are disciplines wired into the tools, not into anyone's habit.

The CI pipeline makes every other loop safe to change. An agent can push a fix at 03:00 UTC and the fix ships before anyone wakes up.

## ARQ + swarms + parallelism

The interactive system runs **15 concurrent agent containers** (`MAX_CONCURRENT_TASKS=15`). Most AI-team setups run one chatbot at a time. Fifteen is not a vanity number — it is what is required to keep a 14-person company's worth of Slack threads, scheduled tasks, and ARQ items moving in parallel.

**Worktree isolation.** Each sub-agent gets its own git worktree under `.claude/worktrees/<task-id>` so two agents working on the same repo cannot stomp each other's branches. The worktree pattern was hard-won: before it landed, parallel agents would commit to the wrong branch when HEAD drifted mid-session. Now an agent does `git checkout <their-branch>` immediately before staging, and the worktree contract enforces the isolation. Build agents are wired with `isolation: "worktree"` by default; Notion-only research agents run unisolated because they do not touch the filesystem.

**Dispatch governors.** Three guardrails prevent a runaway swarm. First: per-host-session cap of 8 sub-agent dispatches (override via `NANOCLAW_HOST_DISPATCH_CAP`). A soft warning fires at 5 dispatches; exceeding 8 returns exit 7 and refuses the dispatch. Second: ARQ daily cap of 10 dispatches (`NANOCLAW_ARQ_DAILY_CAP`). Hitting the cap stops the dispatcher in `apply` mode and reports the queue depth to admin. Third: a cross-source burst detector (`scripts/dispatch-burst-detector.py`) joins the per-host-session counter and the ARQ daily count and fires admin ping when the union crosses a threshold — catches the failure mode where the host loop and the ARQ dispatcher both fan out on the same morning.

**The cost of getting parallel wrong.** Today's session surfaced a subtle one. The `Bash` tool's working directory does not persist across calls — `cd /path/to/repo && ...` in one tool call has no effect on the next. An agent building in a worktree had been issuing `cd <worktree>` then a separate `npm run build`, which ran in the wrong directory. The fix is the rule: chain `cd` with the work in a single bash call, or pass absolute paths. The meta-fix: when a parallel agent's behavior surprises you, audit the tool contract before the logic.

**Pipeline bottleneck.** Running 4+ parallel feature branches at once chokes auto-promote. Smoke watches serialize on `flock`; five branches in flight queue end-to-end for ~2.5 hours. `[hotfix]` shortens the watch to 5 minutes, and `promote-to-prod.sh --auto --hotfix <branch>` can inject a branch into the front of the queue. Parallelizing the smoke watch is on the roadmap.

The shape worth noting: parallelism is not free, and it is not the model that makes it valuable. The model is fast. The shipped, tested, deployed code path is what is slow. The investment in dispatch governors, worktree isolation, and the auto-promote pipeline is what lets 15 agents work concurrently without melting the host.

## Observability

If the agents are doing the work, the only thing left for humans to do is read what happened.

**The audit log.** `audit_log` is a SQLite table inside `store/messages.db` with one row per action: sender, agent, model, tool calls, reasoning trace, cost. As of this writing the table holds 63,535 rows. The table is queryable from any agent (read-only) and from the host (read-write). When an investor or a teammate asks "why did the bot send that message," the answer is one query away. Audit log retention is unbounded by design; storage is cheap, and the value of a one-year-old audit trail is "did we miss this back then" — exactly the question SQLite can answer in milliseconds.

**JSONL telemetry layers.** Three append-only logs sit next to the audit log: `logs/model-routing.jsonl` (every routing decision — Haiku vs Sonnet vs Opus — with the score that produced it), `logs/anthropic-cost-telemetry.jsonl` (per-container Anthropic cost attribution from response headers, joined by `container_src_ip` and time window), and `logs/container-context.jsonl` (which skill ran for which thread). The point of three separate JSONL files instead of one wide table is composability — each log is uniform (one JSON object per line, fixed schema), each is independently rotatable, and the `daily-anthropic-cost-monitor.py` script joins them on-demand to produce the morning cost digest.

**Self-modification monitoring.** The R2 anomaly detector watches for unauthorized code changes (commit-author drift, file-mode flips on root-owned files, semgrep rules silently disabled). It runs hourly, in shadow mode for the first 30 days of each rule, then flips to active and starts firing admin pings. The whole point is to catch the failure mode where the system modifies itself in ways an operator did not authorize — an important property in a system that can ship its own code.

**The dashboard as the daily interface.** Aki's morning is a 30-second scan of the 09:00 UTC dashboard post in `#ai-projects-nanoclaw-admin`. Items that are green get a glance; items that are yellow or red have an inlined next-step command. This is the inverse of the usual ops pattern — most teams keep Grafana open and hope to notice. We keep nothing open and trust the system to summon a human when summoning is warranted.

## Closing — today

I want to close with what happened on 2026-05-13, because it is the cleanest example of why the loops matter.

At 11:51 UTC, a python3 process inside an interactive `claude` session ate 19 GB of RAM and got OOM-killed. At 12:08 and 12:35, the same pattern repeated — three OOM kills in 44 minutes. Root cause was an ad-hoc port of the `bitsafe-gdrive-permissions` full-Drive accumulator: `all_files = []; for page in pages: all_files.extend(page)`, which works fine on a Heroku dyno serving a slow UI and explodes on the company-wide Drive (tens of thousands of files × an arbitrary permissions array each). The 32 GB host had zero swap. The third kill rebooted the box.

Within four hours, with no human commit-by-commit babysitting:

- 8 GB swap added (`fallocate -l 8G /swapfile`, `vm.swappiness=10`).
- 10 GB cap on interactive `claude` via `systemd-run` transient scope in `/root/.bashrc`.
- 8 GB cap on the cron `host-session` via a self-reexec into a `systemd-run` scope.
- OOM-backoff sentinel at `/tmp/host-session-last-oom`: if a tick exits with rc=137, the next tick within 1800s skips the claude call and pings admin instead of thundering-retrying.
- Dead-man's switch wired to the external uptime monitor.
- A dashboard sidecar counter shape-gate fix (separate finding, same recovery window).
- The autoflow cursor-bootstrap gap identified and fixed — a silent-drop class where a thread's first @-mention queued past `MAX_CONCURRENT_INTERACTIVE=3` would never get processed because the cursor never got written; 16 stuck production threads on the day of the fix.

The dev pipeline auto-promoted the fixes to main. The memory files were updated mid-session, not at the end. The OOM pattern is now documented at `feedback_gdrive-accumulator-pattern.md` so the next agent that touches that code reads "never reproduce `all_files = []; for ...: all_files.append(...)`" before it writes a line.

The autonomous engine is not AI without humans. It is machinery that runs while humans steer — and recovers itself fast enough that humans can stay focused on judgment, not janitorial work.
