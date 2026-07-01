---
title: "Code Factory MVP Spec — 24x7 Autonomous SDLC Pipeline"
slug: code-factory-mvp-spec
type: spec
published: 2026-05-25
audience: [App Developers, Trading Firms]
source: https://www.notion.so/bitsafe/Code-Factory-MVP-Spec-24x7-Autonomous-SDLC-Pipeline-36b636dd0ba581bdafa1d0ec180ec081
---


> 🏭 Code Factory: a 24x7 autonomous SDLC pipeline that turns ideas → research → specs → shipped code with minimal human babysitting. Patterned on NanoClaw's three-queue model (Research Queue → Task Queue → Ship Queue) and the safety rails we've battle-tested in production.

# 1. Vision


A self-sustaining software factory where humans set direction and the agent swarm executes. Three queues run continuously; ideas flow in one side, shipped commits come out the other. Humans approve at high-stakes gates (spec sign-off, prod promote), the system handles everything else.


Core thesis from NanoClaw: the bottleneck isn't agent capability — it's queue discipline, state visibility, and reversibility. Get those right and throughput compounds.


# 2. The Three-Queue Pipeline


## 2.1 Research Queue (RQ)


Inbox for ideas, capability gaps, vendor evaluations, and *unknown skills*. Backed by a Notion database with: Topic, Why Relevant (verbatim source), Source URL, Priority (P0–P3), Status, Owner.


- Entry points: agents auto-file via suggest_research; humans drop links/notes; weekly review promotes high-signal items.
- Triage agent runs every N hours: dedups, scores, drafts a 1-page brief, flags decision-required items for admin.
- Promotion gate: approved items become specs (move to Task Queue); rejected items archive with reason.
## 2.2 Task Queue (TQ) — the SDLC spine


Each task is a Notion row with SDLC-step checkboxes:


1. Spec drafted (acceptance criteria + test plan)
1. Spec approved (human or auto-approve for Tier-4)
1. Build started (worktree claimed, branch created)
1. Tests written + passing locally
1. PR opened + CI green
1. Code review (peer agent or human)
1. Merged to dev → 30-min smoke watch
1. Auto-promoted to prod (with exception-file gate)
1. Shipped (CHANGELOG trailer consolidated, ship-log entry posted)
Schema: Title, Spec (relation), Tier (1–4), Status, Owner agent, Blocker, Worktree branch, PR URL, Acceptance criteria.


## 2.3 Ship Queue / CI/CD


- Dev VM auto-deploys every branch push. CI runs lint + typecheck + unit tests.
- 30-min smoke window watching journalctl on dev. Clean → auto-merge to main.
- Exception-file gate refuses auto-promote when high-risk files change (Dockerfile, DB schema, firewall, major dep bumps) — human-only path.
- Litestream replicates state DB to GCS continuously (~1s RPO). Weekly DR drill restores from replica.
# 3. State Machine


```
idea → researching → spec_drafted → spec_approved → building → in_review → ci_green → on_dev → promoting → shipped
                                              ↓ rejected at any gate → archived (with reason)
                                              ↓ blocked → flagged-to-admin (ask-admin RPC)
```

# 4. Agent Roles


- Triage — dedups RQ, scores priority, drafts briefs, escalates decision-required items.
- Spec — turns approved RQ items into Task rows with acceptance criteria + test plan.
- Build — claims a worktree, implements, writes tests, opens PR. Bounded turn budget; on overrun emits a rescope-handoff.
- Review — independent peer agent: checks acceptance criteria, runs tests, comments on PR.
- Ship — handles dev → smoke → auto-promote, consolidates CHANGELOG trailers, posts ship-log entry.
- Watchdog — heartbeat alarms, stuck-agent detection (max-turns / wall-clock / livelock), budget tripwires.
# 5. Safety Rails (proven in NanoClaw)


- Worktree isolation — every Build agent works in its own git worktree; no in-place edits to shared repos.
- File-claim locks — claim_file / release_file prevent two agents racing on the same path; auto-expire after 25 min.
- Exception-file gate — Dockerfile, DB migrations, firewall rules, major dep bumps refuse auto-merge.
- 30-min dev smoke window — every promote watches dev journalctl for errors before merging to main.
- CHANGELOG trailers — agents write structured commit trailers; orchestrator consolidates on main (no merge conflicts on shared doc files).
- Bounded turn budgets — agents that hit cap emit a rescope-handoff JSON for auto-redispatch (depth ≤ 2, spend cap $5/chain).
- Severity-tagged alerts — critical/warning/info/debug routing keeps signal high in the admin channel.
- Bulk-send + cross-post leak guards — prevents fan-out hallucinations into wrong channels.
# 6. Observability


- Heartbeat tasks for each queue (RQ depth, TQ in-flight, Ship velocity) — alert on drift.
- Daily ship log auto-posted to admin channel (commits shipped, items closed, blockers raised).
- Budget tripwires — Anthropic spend ≥80% (warning), ≥95% (critical).
- Stuck-agent detection — max-turns, wall-clock, livelock, heartbeat-stale fires page admin.
- Litestream + Sunday DR drill — RPO ~1s, RTO under 1 hour.
# 7. Knowledge Layer


- Local SQLite caches for every read-heavy source (Notion, docs, repo code, chat history) — agents query in <100ms, never pay round-trip latency on hot path.
- Hourly cache refresh from canonical sources (Notion = source of truth for specs, GitHub = source of truth for code).
- Unified FTS5 search across all caches — agents discover prior art before reinventing.
- Skills DB (Notion → on-disk cache) — agent capabilities live as versioned skill docs; edit in Notion, sync hourly.
# 8. MVP Scope (4 weeks)


### Week 1 — Foundations


- Notion DBs: Research Queue, Task Queue, Ship Log, Specs (all linked via relations).
- Pick one pilot codebase (small repo, <50 files, has tests).
- Set up dev VM + GH Actions CI for the pilot.
### Week 2 — Agent roles + state machine


- Triage + Spec agents writing to Notion.
- Build agent with worktree isolation + file-claim locks.
- Review agent gating PR merges.
### Week 3 — Ship pipeline + safety rails


- 30-min dev smoke watcher + auto-promote-to-prod.
- Exception-file gate.
- CHANGELOG trailer consolidation.
- Watchdog + heartbeat alarms.
### Week 4 — Throughput tuning


- Run end-to-end: 10 RQ items → 10 shipped commits with zero human intervention on Tier-4 tasks.
- Budget tripwires + ship log.
- Litestream + Sunday DR drill on factory state DB.
# 9. Out of Scope (Phase 1)


- Multi-repo orchestration (start with one repo).
- Customer-facing features (factory builds internal tools first).
- Self-modifying factory (factory editing its own agent code) — defer to Phase 2.
- Cross-org PRs / external contributors.
# 10. Open Questions


1. Which pilot codebase? (Suggest: a small internal tool we already maintain.)
1. Spec approval policy: auto-approve Tier-4 (doc / refactor / housekeeping)? Human-only for Tier 1–3?
1. Review agent: peer Claude, or different model for adversarial review?
1. Budget: target $/shipped-commit? (NanoClaw runs ~$X/day; factory's per-output cost should be lower as throughput rises.)
1. Failure escalation: ask-admin RPC for blockers, or queue for daily human review?
# 11. Success Metrics


- Throughput: shipped commits / week (target: 10+ by end of Week 4).
- Human-touch ratio: % of Tier-4 commits shipped with zero human intervention (target: >90%).
- Cycle time: RQ entry → shipped (target: <48 hours for Tier-4, <1 week for Tier 2–3).
- Rollback rate: % of auto-promoted PRs that needed revert (target: <5%).
- Budget: $/shipped commit (track trend; should decline as throughput rises).
# 12. Core Integrations


## 12.1 Slack


- Inbound: humans drop ideas, paste links, give direction in a designated #factory channel. Trigger word wakes the Triage agent.
- Outbound: all agent comms (spec drafts, PR links, ship-log entries, heartbeat alarms) post to #factory or thread-reply to the originating message.
- Admin escalations: ask-admin RPC (blocks until human replies) vs ping-admin fire-and-forget — same two-surface model as NanoClaw.
- Guard rails: bulk-send guard (>3 external channels needs 3-of-3 approval gate), cross-post leak check.
## 12.2 Notion


- Source of truth for: Research Queue, Task Queue, Ship Log, Spec docs, Skills DB.
- Agents write via Notion API (MCP). Reads prefer the local SQLite cache (hourly refresh); API only for writes and cache misses.
- Notion AI Q&A responder for ad-hoc queries against company knowledge (skills, specs, decisions).
- Skills DB: factory agent capabilities live as versioned Notion rows; on-disk cache refreshed hourly. Edit in Notion, not on disk.
## 12.3 GitHub


- Build agent creates a branch + worktree, commits, opens PR. Authenticated via per-user PAT stored in Secret Manager (auto-configures gh CLI).
- GH Actions CI: lint, typecheck, unit tests on every branch push. Dev-deploy job fires on green.
- Review agent uses gh CLI to comment + request changes on open PRs.
- Ship agent merges via gh pr merge after smoke watch passes. Exception-file gate blocks auto-merge on high-risk files.
- Source cache: repo code indexed to local SQLite for fast symbol/pattern search without cloning every run.
# 13. Swarm Architecture


The factory runs a lightweight swarm: a team lead orchestrates role-specialized agents, each in its own bounded-turn container. File-claim locks prevent race conditions; inbox/outbox message passing is the only inter-agent interface.


- Team lead — pulls next task from TQ, dispatches role agents, monitors heartbeats, handles escalations.
- Role agents (Triage, Spec, Build, Review, Ship, Watchdog) — single-purpose, one task at a time, report back to team lead.
- Parallel builds — multiple Build agents work on independent tasks simultaneously; file-claim locks prevent collision on shared files.
- Rescope-handoff protocol — agents that hit turn-budget emit a structured JSON handoff; host auto-dispatches sub-tasks (depth ≤ 2, $5/chain spend cap, loop detection).
- Sub-agents never call send_message — only the team lead surfaces output to humans.
- Team lifecycle: TeamCreate on task start, TaskUpdate to claim/complete, SendMessage for peer DMs, TeamDelete on cleanup.
# 14. Model Router


Route each agent invocation to the cheapest model that can do the job reliably. Saves 80–95% on token cost vs defaulting everything to Opus.


### Routing table (default policy)


- Haiku 4.5 — Triage (dedup/score/classify), heartbeat checks, pre-flight scripts, simple lookups, summarization.
- Sonnet 4.6 — Spec drafting, Build (standard tasks), Review, Ship orchestration, most Research briefs.
- Opus 4.7 — Complex multi-file refactors, security reviews, architecture decisions, any task flagged Tier-1 by the team lead.
### Escalation rules


- Auto-escalate to Sonnet if Haiku produces a malformed output (JSON parse fail, missing required fields) after 1 retry.
- Auto-escalate to Opus if Sonnet hits a rescope-handoff for the same task twice (signal: task is harder than classified).
- Team lead always runs Sonnet minimum — it's the coordination layer; cost here is amortized across all sub-agent work.
### Implementation


- Router is a small config layer (JSON or Notion row per agent role) — model is a property of the task tier + agent type, not hardcoded.
- Overrideable per-task: TQ row can specify model=opus to force Opus on a specific build.
- Budget tripwire: if Opus spend > threshold this hour, hold Opus queue and alert admin before accepting new Opus dispatches.
# 15. Agent-to-Agent Communication via MCP


Each agent exposes and consumes a small set of MCP tools. Inter-agent calls look identical to human-tool calls — same auth, same transport, same structured I/O. This means any agent can be a client, a server, or both simultaneously.


### Topology


- Team lead exposes a dispatch MCP server — role agents call it to claim tasks, report completion, and escalate blockers. This is the single coordination bus; no peer-to-peer spaghetti.
- Shared-resource agents (Knowledge Cache, Notion writer, GitHub actor) expose MCP servers — other agents consume them without knowing the underlying implementation.
- Watchdog exposes a health-check MCP server — any agent can call report_heartbeat(agent_id, status) or query_stuck_agents().
- Agents discover each other via a registry MCP tool (list_agents) — same pattern as NanoClaw's nanoclaw MCP list_agents today.
### Message passing vs MCP — when to use which


- MCP tool call — structured request/response with typed schema. Use for: task dispatch, cache reads, health checks, GitHub/Notion writes. Fast, synchronous, composable.
- SendMessage (inbox/outbox) — async, threaded, free-text. Use for: escalations that need human-readable context, peer DMs between agents working a shared spec, long-running status updates.
- Rule of thumb: if the receiver is an agent and the payload is structured → MCP. If the receiver might be a human or the payload is narrative → SendMessage.
### Safety contracts


- Every MCP server exposed by an agent is read-only by default; write tools require an explicit capability declaration in the agent's skill definition.
- No agent can call another agent's MCP server unless it appears in the registry with status=active. Dead/stuck agents are de-registered by the Watchdog.
- MCP tool calls between agents are logged to the factory's observability store — same as human-originated tool calls. Full audit trail.
- Circular call detection: if agent A calls agent B which calls agent A, the registry returns a loop-detected error and pages the Watchdog.
### MVP implementation


- Phase 1: team lead ↔ role agents only (star topology). No peer-to-peer until Phase 2.
- MCP servers run as lightweight HTTP endpoints inside each agent container (stdio or SSE transport, same as Claude Code MCP today).
- Registry is a simple Notion DB row per agent (agent_id, mcp_endpoint, capabilities[], status, last_heartbeat). Watchdog polls + de-registers stale entries.
# 16. Additional MVP Requirements (NanoClaw Lessons Learned)


> ⚠️ These 17 requirements emerged from reviewing bitsafe-ai-docs (architecture, autonomous engine, cost discipline, monitors) after building NanoClaw. All are considered MVP — skipping any one of them is how you repeat our past incidents.

## 16.1 Cost Discipline & Model Routing


- **Haiku triage layer** — before spawning a full agent container, run a Haiku classifier ($0.0006/call) that routes to one of three paths: direct_answer (respond inline, no container), cache_lookup (search SQLite caches, respond), full_agent (spawn container). Asymmetric miss cost: routing a hard question to direct_answer costs more than routing an easy one to full_agent — so the threshold should be conservative (HAIKU_BOUNDARY ≈ 0.08). Deploy in shadow mode for 2 weeks before going live to calibrate without impact.
- **Per-spawn cost attribution** — every container spawn writes two JSONL records: cost-telemetry.jsonl (API call cost, model, token counts) and container-context.jsonl (chat_jid, skill name, thread_ts). Join on container ID so every dollar resolves to a specific skill/thread. Without this you cannot debug cost spikes and you fly blind.
- **Tier-aware pricing** — track context window tier from day 1. Opus standard (≤200K tokens) vs extended (200K–1M tokens) costs 2× input price. One misconfigured default context window caused $3,744 in silent overcharges before we noticed. Log tier alongside every API call; alert if a task unexpectedly hits extended tier.
- **MTD auto-throttle** — three states keyed on month-to-date spend vs budget: Normal (<70%): route normally. Warning (70–90%): downroute Opus→Sonnet, Sonnet→Haiku where possible, alert admin. Hard (>90%): force all routing to Haiku except tasks with an explicit model override in their Notion row. This is the last line of defense against runaway spend.
- **Per-spawn cost alerts** — after each container exits, check its total cost against thresholds: ≥$3 = warning ping to admin, ≥$10 = critical ping. 30-minute cooldown per group to avoid alert storms. This catches runaway single invocations before they compound.
- **Hourly cost-tick** — each hour, compare last-hour spend to trailing 24h average per-hour. Spike >2.5× AND last-hour >$5 = warning. Spike >5× AND last-hour >$20 = critical. This catches sustained runaway patterns that individual spawn alerts miss.
- **Runaway channel detector** — track spawns-per-chat_jid; cross-reference Slack API to detect archived or zero-member channels. An archived channel triggered 1,099 spurious spawns in NanoClaw before we added this check. Kill the trigger and alert admin when a channel is inactive but still generating agent invocations.
## 16.2 Observability & Monitoring


- **Cron-success check** — for every scheduled cron, maintain a log file updated on each run. A health monitor checks: is log mtime fresher than interval × 1.5? If not, fire a warning ping. Silent cron failures are the most common class of undetected breakage — a monitor that runs but doesn't log is invisible without this check.
- **State-file freshness check** — any stateful agent writes a data/*-state.json on each run. A central monitor compares each file's mtime to its expected cadence (defined in a config map). Stale state file = agent is silently broken. Pair with cron-success check; together they catch both the cron not running and the cron running but failing to update state.
- **Handled-check sweep** — weekly scan of the admin channel: for each alarm, classify as HANDLED (human reply in thread, Tasks DB row created, commit reference present, or triggering condition cleared) or UNHANDLED. If UNHANDLED count > threshold → ping admin. This catches the silent-failure class where monitors run and post but humans don't act.
- **Action-items extraction** — admin-bot responses must include a structured '## Action items filed' section listing any Tasks DB rows created. A post-hook scanner reads this section and verifies the rows exist. Implicit recommendations that don't get filed are invisible to the pipeline. Enforce the template; scan for compliance.
## 16.3 Operational Safety Rails


- **OOM guards** — run agent containers under systemd-run with a hard memory cap (8GB recommended). Track exit codes: rc=137 = OOM kill. Implement OOM-backoff sentinel: if a container OOM-killed within the last 1800 seconds, skip the Claude API call and return a graceful error. Without this, OOM loops saturate the host and cascade into unrelated failures.
- **Mass-deletion pre-commit guard** — pre-commit hook refuses commits with >20 deleted files OR >2000 net lines removed. Requires ALLOW_MASS_DELETE=1 env var to override. This catches runaway refactors and accidental rm -rf before they hit the repo. Code review doesn't catch what never appears in a diff.
- **Schema-as-perimeter** — agents operate strictly within a frozen database schema they cannot modify. Only an Architect-tier agent (human-approved, explicit permission) can alter schema. This prevents agents from silently adding columns, dropping indexes, or reshaping data to fit their current task. Schema stability is what makes the system auditable.
- **Hotfix lane** — commits with '[hotfix]' in the message get a 5-minute smoke window instead of the standard 30-minute dev smoke before auto-promote. Skips the 30-minute rate-limit gate as well. This allows critical production fixes to ship in ~10 minutes end-to-end while preserving all other safety checks.
## 16.4 Skills Architecture


- **Skills as versioned Notion rows** — each skill is a row in the Skills DB with SKILL.md content and scheduled_tasks frontmatter. A reconciler runs hourly, syncing from Notion to three disk paths on each agent host. Agents edit Notion; disk is read-only cache. New skills require zero code releases — they're live within one reconciler cycle. NanoClaw manages 74+ skills this way.
- **Self-modification monitoring** — an R2 anomaly detector watches for signs that agents are modifying their own runtime: commit-author drift (non-human committer on CLAUDE.md / safety-critical files), file-mode flips on root-owned files, semgrep rules silently disabled. Run in shadow mode for 30 days (log anomalies but don't block) before activating hard blocks. This is the safety net for agents that try to subvert their own constraints.
---

> 📚 Source: `github.com/Akibalogh/bitsafe-ai-docs` — articles 02-architecture, 03-autonomous-engine, 06-cost-discipline, 07-monitors-and-alerts. Compiled 2026-05-25.

# 17. Phased Roadmap


> 🗺️ This section supersedes §8 MVP Scope. All features from §1–16 are classified here by phase. Phase 1 = can't operate safely without it. Phase 2 = meaningfully better. Phase 3 = self-improving system.

## Phase 1 — MVP (Weeks 1–4): Working Factory


Goal: a pipeline that takes tasks from Notion RQ → shipped PR with human gates. Every item here is "can't operate safely without it."


### Core Pipeline & Agents


- Three-queue pipeline: Research Queue → Task Queue (SDLC checkboxes) → Ship Queue, all in Notion DBs
- Agent roles: Triage, Spec, Build, Review, Ship, Watchdog, Team Lead (orchestrator)
- Slack trigger → container spawn → thread reply
- GitHub: branch-per-task, PR on complete, GH Actions CI (lint / typecheck / unit tests on every push)
- Dev→prod topology: 30-min dev smoke, auto-promote listener, exception-file gate (Dockerfile / DB migrations / firewall rules → human-only)
### Swarm Infrastructure


- Star topology: Team Lead + role-specific sub-agents
- Worktree isolation per sub-agent (no cross-agent file collisions)
- File-claim locks (claim_file / release_file) to prevent race conditions on shared resources
- Bounded turn budgets + rescope-handoff JSON (depth ≤ 2, $5/chain spend cap, loop detection)
- Agent-to-agent MCP: dispatch bus, shared resource agents (Knowledge Cache, Notion writer, GitHub actor), Watchdog health-check MCP, agent registry
### Model Routing


- Config-driven defaults by task type: Haiku for triage/heartbeats, Sonnet for build/review/ship, Opus for Tier-1/complex only
- Per-task model override in Notion TQ row
- Manual override keyword ("use opus") passes through the config gate
### Cost Discipline (must-have from day 1)


- Per-spawn cost attribution — two JSONL records per container (cost-telemetry + container-context), joinable on container ID
- Tier-aware pricing — log context window tier (standard vs extended) with every API call; alert if task unexpectedly hits extended tier
- MTD auto-throttle — 3 states: normal (<70%), warning (70–90% → downroute), hard (>90% → force Haiku)
- Per-spawn cost alerts — ≥$3 warning, ≥$10 critical, 30-min cooldown per group
### Safety Rails


- CHANGELOG trailers in commit body (not file); consolidator script runs post-merge
- Mass-deletion pre-commit guard (>20 deleted files / >2000 net lines → refuse; ALLOW_MASS_DELETE=1 to override)
- OOM guards — systemd-run 8GB memory cap, rc=137 detection, 1800s OOM-backoff sentinel
- Schema-as-perimeter — agents operate within frozen schema; only Architect-tier (human-approved) can alter
### Observability


- Severity-tagged admin channel alerts (critical / warning / info / debug)
- Cron-success check — log mtime must be fresher than interval × 1.5; warning ping if not
- State-file freshness check — data/*-state.json vs expected cadence config; stale = agent silently broken
- Dead-man's switch — 1-minute heartbeat → BetterStack external monitoring
### Knowledge & Skills


- Notion as source of truth: RQ DB, TQ DB, Ship Log DB, Specs, Skills DB, Agent Registry
- Skills as versioned Notion rows — edit Notion, reconciler syncs hourly to disk; new skills live in one cycle, no code release
- Local SQLite caches (Notion, Slack) with FTS5 unified search — <100ms lookups before any API call
- Litestream GCS replication (~1s RPO) for the messages DB
---

## Phase 2 — Optimization (Weeks 5–8): Cost Control & Visibility


Goal: cut per-task cost 40%+; ensure no alert goes unnoticed; get full financial visibility across the factory.


- **Haiku triage layer** — shadow mode weeks 5–6 (log decisions, don't act), live weeks 7–8. HAIKU_BOUNDARY ≈ 0.08. Routes to direct_answer / cache_lookup / full_agent before spawning a container.
- **Anthropic account cost tracking** — pull spend data from the BitSafe Eng Claude account API (Anthropic usage dashboard API). Reconcile with per-spawn attribution JSONL to get a full picture: API-reported spend vs internal attribution. Discrepancies surface unattributed calls. Not blocking for MVP but essential before the factory handles serious volume.
- **Hourly cost-tick monitor** — spike >2.5× trailing 24h avg AND last-hour >$5 = warning; >5× AND >$20 = critical
- **Runaway channel detector** — track spawns-per-chat_jid; cross-ref Slack API for archived/zero-member channels; kill trigger and alert
- **Hotfix lane** — [hotfix] in commit → 5-min smoke vs 30-min; ships in ~10 min end-to-end
- **Handled-check sweep** — weekly: classify every admin channel alarm HANDLED or UNHANDLED; ping admin if UNHANDLED > threshold
- **ARQ swarm governors** — per-session cap (8 concurrent containers), daily cap (10 ARQ dispatches), cross-source burst detector
- **Daily health dashboard** — 09:00 UTC, 15-section report: queue depths, cost, agent health, cron success, open alarms
- **Tiered context loader** — load CLAUDE.md and skills cheatsheet at varying detail levels by task type (context shrinkage to stay under standard tier)
---

## Phase 3 — Hardening (Weeks 9–12): Self-Improving System


Goal: the factory monitors and polices itself; humans review outputs, not operations.


- **Action-items extraction** — enforce ## Action items filed section in admin-bot responses; post-hook scanner verifies Tasks DB rows exist
- **Self-modification monitoring** — R2 anomaly detector: commit-author drift, file-mode flips on root-owned files, semgrep rules silently disabled. Shadow mode 30 days → hard blocks active.
- **Full DR drills** — weekly Litestream restore test (Sunday 08:00 UTC); automated pass/fail ping to admin
- **Per-skill cost breakdown** — weekly report: cost per skill derived from attribution JSONL + Anthropic account API reconciliation; surface the expensive ones
- **ARQ feedback loop** — completed task patterns → new skill proposals filed automatically in Research Queue; factory learns its own workflows
