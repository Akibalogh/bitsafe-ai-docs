---
title: "Working With NanoClaw — Personas, Alerts, Memory, Decision Support, and How Humans Teach the AI"
slug: 05-working-with-nanoclaw
series: How BitSafe Runs on Notion
part: 5
published: 2026-05-14
audience: [App Developers, Trading Firms, Investors, Liquidity Providers]
---

# Working With NanoClaw — Personas, Alerts, Memory, Decision Support, and How Humans Teach the AI

The first four parts of this series described what NanoClaw *is*. This part is about what it's like to *work with*. If you're an engineer deciding whether to build something like this, the architecture matters. If you're deciding whether your team would actually use it after the novelty wears off, this is the part that decides it.

> Humans collaborate by remembering. NanoClaw collaborates by never forgetting.

Most "AI in the workplace" stories are about a smarter chatbot. The interesting story is what changes when the AI shows up across every surface where the work happens, with infinite recall, continuous follow-up, and no social cost to interrupting it. The model isn't doing the heavy lifting. The relationship is.

## Why this feels different

Six months in, the deltas between "team with NanoClaw" and "team without" aren't what we expected. We thought we were buying a faster assistant. We got a force multiplier. Eight ways it changes the day:

1. **Perfect memory.** It never asks "what did we decide last quarter?" It quotes you exactly, surfaces the dissent in the room when you made the call, and flags it when the rationale stops applying.
2. **Continuous follow-up.** Commitments don't fall through. The bot tracks "you said you'd ping X by Y" and surfaces it the day Y arrives. The system of things you owe the world is no longer your prefrontal cortex; it's a database with cron jobs.
3. **Zero context-switching cost.** It holds a hundred simultaneous threads with full context each. Humans lose twenty-plus minutes per switch. The bot loses zero.
4. **Async-first work.** Fire a task at midnight, wake to results at 8am. Work happens in your absence — sub-tasks dispatched, errors handled, output delivered.
5. **Cross-domain translation.** Engineering speaks finance via the right persona; finance hears engineering's constraints in an actionable register. What used to be a person on the leadership team is now a tool.
6. **Always-on niche expertise.** Legalbot at 3am on a Saturday. Security review between flights. HR without scheduling. The bottleneck on niche expertise used to be a calendar.
7. **No social cost to asking.** You can bug the bot freely. It doesn't get annoyed, doesn't compute "is this worth their time," doesn't gossip. Junior team members stop self-censoring dumb questions; senior members stop self-censoring tactical asks.
8. **Auditable by default.** Every action is logged. Post-mortems become reconstruction, not detective work. "What happened at 14:23 UTC on the deploy" is a query, not a meeting.

The rest of the article shows the mechanism behind each delta. Four interfaces — who you talk to, what gets pushed to you, what stays, and how you teach it. The leverage is in how they compose.

## The personas you talk to

> We didn't build one AI. We built a cast.

The active interface — the one most people picture when they hear "AI assistant" — is the conversation. NanoClaw's distinguishing move is that the conversation isn't with one entity. It's with a cast of *personas*, each with a name, a voice, an icon, and a memory namespace, all running on the same agent substrate. People-modeled and function-modeled personas are equal-status examples of one pattern: vary the system prompt, the skill assignment, the memory namespace, and the sender identity. Substrate uniform; surface differentiated.

**People-modeled personas** are recognizable thinking styles, grounded in a corpus.

- **Naval** (in the spirit of Naval Ravikant) is the first-principles synthesizer. Brief, asks questions, network-thinking, uncomfortable with consensus. Summon Naval when a decision feels too easy — when the room has lined up but nobody has stress-tested why. The corpus lives at `data/naval-corpus/` (Almanack, Venture Hacks essays, podcast transcripts).
- **Noob Saibot** (the Mortal Kombat shadow ninja) is the adversarial red-team. Argues against any proposal by default. Naval summons Saibot when his own synthesis feels too clean — "make the strongest case against this." Saibot has earned his keep most clearly on security review, where the cost of a missed objection is high and the cost of an extra round of paranoia is low.
- **Matthiasbot** is a retrievable knowledge base of Matthias Frank's published Notion information-architecture work, sourced from his website and YouTube channel. Grounds the bot in the framework (PARA, atomic databases, rollups vs. relations) so BitSafe agents can answer Notion-IA questions without scheduling time with Matthias. Every thread opens with the disclaimer: *"I'm Matthiasbot, trained on Matthias Frank's public content, not Matthias himself."*

**Function-modeled personas** are domain roles.

- **legalbot** is a contract analyzer, shipped 2026-05-13 at `/root/nanoclaw-skills/legalbot/`. Reads a Google Drive link (READ-ONLY — never writes back to the source), benchmarks against BitSafe's standard positions in Notion principle pages, and produces a separate redline grouped by priority (must-fix, material-risk, nice-to-fix). What makes legalbot trustworthy is the two-round independent-agent review: round one drafts; round two is a fresh agent with *no context from round one* that checks for self-introduced conflicts.
- **hrbot** for HR questions. Same pattern, different corpus.

All of them run on the same Claude substrate (Opus 4.7 today, whatever ships tomorrow). What differs is the system prompt, the skill assignment, the memory namespace, and the voice. The personas form a graph rather than a hierarchy: any persona can dispatch any other via MCP. A typical strategic-decision dispatch:

```
Aki → Naval ("should we partner with X?")
       ↓ (~30 seconds in)
       Naval → Noob Saibot ("strongest case against partnering with X")
       ↓ (~60 seconds later)
       Naval ← Saibot's three best objections
       ↓
       Aki ← Naval's synthesized recommendation, with Saibot's objections folded in
```

Round-trip: ~90 seconds. Cognitive load on Aki: read one synthesized message and push back on what doesn't land. The premortem move — "imagine this fails in six months, what does the autopsy say" — is one of the canonical Saibot dispatches; we ship `premortem` as a standalone skill so the pattern is available even when Naval isn't in the loop.

The personas aren't architectural primitives — they're examples of a pattern. The pattern: take a shared agent substrate, vary the system prompt and the grounding corpus, give the result a name and a voice, route by intent. Other companies will build their own cast.

## The alerts you receive

> The chatbot framing misses the most valuable part: the passive alert interface is often more useful than the active conversational one.

About a third of the team's interaction with NanoClaw is *outbound* — the bot tells them something they didn't ask. This is the passive interface, and it's where the system pays for itself. Thirty-two active scheduled tasks, four categories.

**Push alerts (proactive) — fired when a check trips.**

- **Daily Health Dashboard** at 09:00 UTC. The most-read message of the day. Walks 35+ checks (data-source freshness, search latency, vector embedding coverage, Slack sync, container health, secret-file modes, pipeline state) and posts a structured table to `#ai-projects-nanoclaw-admin`. Degraded `:warning:`, broken `:x:`, healthy `:white_check_mark:`. The dashboard IS the dashboards — 35+ separate background workers in some other system, here 35+ alert subscriptions in one post.
- **Daily Anthropic Spend Monitor** at 08:00 UTC. Reads yesterday's CSV, computes total by model and cache-hit rate, compares to trailing 7-day average, projects month-end. Fires red alerts when cache hit drops below 80%, daily spend ≥ 2× trailing, or MTD pacing exceeds 90% by day 15. Cooldown-gated so a single bad day doesn't generate eight pings.
- **Security alarms**: R4-ac admin-compromise monitor, R2 audit-log anomaly detector, dead-man's-switch heartbeat to BetterStack (if NanoClaw stops checking in, BetterStack pages Aki out-of-band).
- **Push watchdog**: unpushed commits older than 6 hours fire an admin ping. If something's done, it should be in `origin`.
- **Scheduled-task failures**: three consecutive runs trip a circuit breaker and ping admin with the failure category.

**Digests (scheduled summaries) — fired on cadence regardless of state.** Daily BD digest, daily standup kickoff, weekly company brief at Friday 15:00 UTC, weekly sales leaderboard at Monday 13:00 UTC, per-user daily digests of new Notion pages / in-progress tasks / active projects for each leadership-team member, monthly investor update drafted by sub-agent and reviewed by human.

**In-thread reactions — micro-signals, no message body.** `:hourglass_flowing_sand:` lands on a triggering @-mention within seconds so the sender knows the bot saw it. Removed when the bot speaks. If the bot has nothing to say — informational @-mention, dedup with an existing message — the hourglass is replaced by a `:+1:` so the message doesn't look hung. This is a real bug we shipped on 2026-05-13 (`feedback_hourglass-cleanup-on-no-reply.md`); informational @-mentions kept stranded hourglasses for hours before the fix. Container completion status (success / partial / failure) is also reactioned onto the trigger for ambient awareness.

**Escalation alerts — small in count, high in priority.** ARQ circuit breakers when the research-queue dispatcher hits its daily ceiling. Container retry-budget exhausted when one thread fails three same-category times in 30 minutes. Autoflow silent-drop detector when a triggering @-mention never gets a cursor written — the class we hit and fixed on 2026-05-14 (`feedback_autoflow-cursor-bootstrap-gap.md`). Goals scan gaps when something in Notion Goals doesn't have a downstream ARQ item.

Three design principles cut across. **Severity tiers** map alerts to delivery surfaces: info to admin channel, warning to admin DM, critical paged out-of-band through BetterStack. **Cooldown + dedup** is enforced per source — `scripts/ping-aki.sh --source <name>` checks a state file before firing so a repeat condition doesn't spam. **Batching** is preferred over staccato: dashboards land in one post per day, not 35 pings.

Each alert is a *job-shaped feedback loop*. You don't monitor data-source freshness manually because NanoClaw tells you when it degrades. You don't remember to check MTD spend because the daily monitor will alarm if pacing breaks. The headspace previously spent on "did I check X today" is reclaimed.

## The memory that accumulates

> The AI doesn't get smarter. We get better at teaching it.

The third interface is the one nobody sees: the persistent file-based memory at `/root/.claude/projects/-root-nanoclaw/memory/`, indexed by a flat `MEMORY.md`. 240+ files at this writing. Four types:

- **`user_*`** — who someone is, how they work. `user_aki.md` carries Aki's role, communication preferences, the patterns he's enforced.
- **`feedback_*`** — corrections that became durable rules. A bug surfaces, a human corrects, a memory file is written, future sessions never make the same mistake. Today's session alone added four: `feedback_notion-url-workspace-prefix.md` (Notion API URLs need a workspace prefix before sharing with humans), `feedback_skill-built-but-not-scheduled.md` (shipping skill code isn't enough — the `scheduled_tasks` row is a separate insert), `feedback_gdrive-accumulator-pattern.md` (a Drive permissions sync loaded its corpus into memory and OOM-killed `nanoclaw-01` three times on 2026-05-13; the lesson is streaming generators, not accumulators), `feedback_autoflow-cursor-bootstrap-gap.md` (the silent-drop class where the first @-mention in a thread never gets a cursor because dispatch and process disagree on LIMIT).
- **`project_*`** — in-flight initiatives and their *why*. Each entry includes a one-line rationale so future readers can judge whether the file is still load-bearing.
- **`reference_*`** — durable pointers to external resources. Page IDs, dashboards, runbooks.

Mid-session writes are the discipline. When a sub-agent learns something non-obvious, the memory file is written *immediately*. Today's four memory files were written *during* the sessions that surfaced each bug — the batch reflection at the end of a long session never reliably happens.

This is worth naming because it's the **counter-narrative to RAG**. The fashionable answer to "how should an AI agent remember things" is vector retrieval. We don't do that for institutional memory. We use *propositional* memory: written rules, loaded into the prompt at session start, *heeded* rather than retrieved. The agent doesn't search its memory — it reads its memory the way a new employee reads the onboarding doc. The rules are in the context window, not in a similarity score.

Skills complete the picture as procedural memory. SKILL.md frontmatter plus composable code under `/root/nanoclaw-skills/<name>/`. A `feedback_*` file teaches the agent what *not* to do; a skill teaches it *how* to do something repeatable.

## Decision support

The most distinctive use of NanoClaw isn't task automation — it's decision support. The Naval + Noob Saibot pair is the canonical workflow. A strategic question goes to Naval; Naval synthesizes; if the synthesis feels too clean, Naval dispatches Saibot for the strongest counter-argument; the final output is the synthesis with the best objection folded in. Two specific techniques have earned their place.

**Premortem**, in the Gary Klein sense, lives as a standalone skill at `/root/nanoclaw-skills/premortem/`. Before a major commitment — a deal close, a hire, a deprecation — Saibot is asked to imagine the failure mode six months out in vivid detail (the specific customer that churned, the specific bug, the specific competitor move) and walk *backwards* to what we should have seen today. The vividness matters: an abstract premortem produces hedging; a vivid premortem produces actions.

**Reference-class forecasting** is in flight. The M4 reference-class library is an ARQ initiative to populate base rates for the decisions BitSafe makes repeatedly — validator partnerships close at this rate, infrastructure migrations take this long, marketing channels with these characteristics produce this CAC. When it ships, Naval will surface the base rate alongside the synthesis: "similar deals close at 30%, here are the three closest analogs."

The longer arc: the ARQ research item on the AI Board Member (`35a636dd-0ba5-8162`) carries the "Findings: AI Board Member — Competency Gaps & Decision Support Framework" page that scoped what AI decision support should mean for BitSafe. Naval and Noob Saibot are the operationalization of that framework. The framework will outlive the personas; the personas will be replaced as we learn what works.

## The HITL teaching loop

The fourth interface is the most consequential and the least visible: how humans teach NanoClaw. Human-in-the-loop in our use isn't a UX detail — it's the mechanism by which the system gets less wrong over time.

**AI proposes, human disposes.** The bot drafts; humans QA; the publish action is a deliberate gesture. For Notion pages that codify *policy or rules awaiting human debate*, drafts are titled `PROPOSED — <Original Name>` so the owner reviews in place, then renames to ship. The convention is scoped, not blanket: evidence-based regenerations of existing pages (an updated commission report, a refreshed investor update) ship as new versions without the prefix — they're not proposals, they're updates.

**Memory files as institutional learning.** This is the loop that pays compound interest. The bot makes a mistake → a human corrects → the correction becomes a memory file → next session, the same class of mistake doesn't happen. Today's four new memory files all came from this loop in a single session — each one a permanent fix for a bug class that would otherwise have repeated.

**Tiered approval gates.** The dev pipeline carries a `[uat]` commit-tag opt-in: when a commit message contains `[uat]`, auto-promote holds the branch until a human green-lights it via a Slack reaction. The default is the opposite — a clean dev run plus a 30-minute smoke watch is enough for promotion. UAT exists for things only a human can evaluate (Slack post quality, Notion page voice, search relevance); auto-promote covers everything else. The hotfix lane shortens smoke to 5 minutes but doesn't skip the gate.

**Two-round independent review.** Legalbot's round-two consistency check is the externally-visible instance of an internal pattern we use whenever bot-authored output ships in a high-stakes context. Round one drafts; round two is a fresh agent with no context from round one. The independence is load-bearing — if round two reads round one's reasoning, it inherits round one's blind spots.

**Ask before X.** Certain actions require explicit human approval: restarting NanoClaw (active agents may be in flight), destructive ops (`git reset --hard`, `git push --force`), external-facing communications. The deliberate counter-balance is the autonomous-loop runtime, which sets `--dangerously-skip-permissions` so the scheduled-task loop doesn't silently stall on a prompt nobody will see. Different runtimes pick different defaults; the default is *trained*, not coded.

**Decide-and-note vs. ask-explicit.** Implementation choices go to AI judgment with a CHANGELOG note; policy, scope, and IAM stay with the human. The quick test: would a competent engineer with full codebase access still be unsure? If no, decide and ship. If yes, ask.

**Escalation paths.** When a sandboxed container hits ambiguity it can't resolve in its own scope, it reaches a human admin through `ask-admin-ferry.py` — posts a question to admin chat and blocks until a human reaction comes back, without breaking egress or scope. The clean separation lets us run containers with narrow tool grants and still keep them un-stuck.

The frame worth ending on: **the AI is like a junior employee.** It works, the human corrects, the correction becomes durable memory, the next time it doesn't make the mistake. The corrections compound. The institutional learning rate of the system is bounded only by the rate at which humans correct it. After six months, the population of memory files is the company's accumulated wisdom about how this particular AI fails — and how it should succeed.

## The two hard limits

Two things NanoClaw doesn't do, and won't, even as everything else expands.

**NanoClaw doesn't talk to customers.** Customer-facing communication stays human-to-human. The bot drafts the email, prepares the answer, surfaces the right context from prior threads — but a human signs and sends. Making a customer talk to a bot feels disrespectful in a way that's hard to walk back: it tells them their time is worth less than ours, and that nothing in the conversation requires creative judgment specific to them. Internal augmentation only. The leverage NanoClaw gives the team is felt on the customer's behalf, not aimed at the customer directly.

**NanoClaw doesn't send money.** No payments, no transfers, no wallet operations, no on-chain transactions, no off-chain disbursements. The reasoning is simple: if there's a bug, we don't want it losing money, sending it to the wrong place, or — worst case — getting hijacked by an attacker who finds a path the bot didn't realize was a path. Financial actions stay behind a human signature.

## Closing

Four interfaces. Personas for active conversation. Alerts for passive notification. Memory for persistence. HITL for collaboration. Most AI tools give you one — the chatbot. NanoClaw gives you four, and the leverage is in how they compose.

A scheduled alert finds a problem; a persona is dispatched to fix it; the fix updates memory; the next time the same class of problem appears, the bot recognizes it and the alert never fires. That loop is the product. Not the model, not the prompt, not the integrations — the loop.

> Most AI tools are smarter chatbots. NanoClaw is a working relationship.

The architecture is in Part 2. The engine is in Part 3. The substrate is in Part 4. This part is the one your team actually feels. A new hire's first week with NanoClaw isn't learning a tool. It's meeting a coworker who already knows everything the company has written down — and who's ready to be taught the next thing.
