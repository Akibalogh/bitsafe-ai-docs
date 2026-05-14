---
title: Building a Company-Wide AI Assistant: Architecture, Security, and Self-Improvement
slug: company-wide-ai-assistant
published: 2026-04-23
audience: Engineering / Founders / CTO
status: published
notion_id: 34b636dd-0ba5-811e-8299-c4e2d37d2b28
---

Most teams using AI today are doing it one person at a time — individual ChatGPT accounts, scattered API experiments, no shared memory. I took a different approach: building a shared, company-wide AI assistant that knows the business, has access to company data sources, and gets smarter over time. Here's what I built and how it works.

## The Core Architecture

The system runs as a multi-user platform on top of a frontier LLM (Claude by Anthropic). Each conversation runs in an isolated Docker container with its own workspace. Containers are ephemeral — they spin up per session — but persistent state lives in mounted volumes: one private volume per user, one shared volume per team channel.

A host orchestration layer handles container lifecycle, message routing, and scheduled task persistence. Scheduled tasks are stored in a host database, not crontab — so they survive container restarts and are manageable via API. The agent surfaces in Slack, is thread-aware, uses @mentions, and can spawn named sub-agents that appear as distinct Slack bot identities for complex multi-step workflows.

The tool interface between the LLM and the host uses the **Model Context Protocol (MCP)**. Every tool call — file reads, bash commands, Slack messages, Notion writes, secret retrieval — goes through MCP servers that the harness exposes to the container over stdio. The LLM requests a tool call; the harness checks the permission tier; if approved, executes it and returns the result. This gives the harness fine-grained control over every action the model takes, with a complete audit trail at the harness layer rather than relying on the model to self-report.

Workspace layout: `/workspace/global` (read-only system config and skills, synced from host), `/workspace/group` (shared team channel workspace — memory, daily logs, conversation archives), `/workspace/user` (private per-user workspace, mounted on every container start — secrets, personal config, scripts). Session state in the user workspace persists across ephemeral containers because the volume is mounted from the host, not the container filesystem. The model is explicitly instructed to write intermediate results and decisions to files rather than holding them in context, which also protects against context rot as conversations grow long.

Not every task needs the same model. A model router directs requests to different tiers based on complexity: lightweight checks and simple summaries go to a fast, cheap model; multi-step reasoning, code generation, and anything requiring judgment goes to a more capable one. The routing logic lives in the harness, not the prompt — so it can't be talked out of it. In practice this cuts costs significantly without any quality regression, because most of the volume is low-complexity work that a smaller model handles fine.

## Why NanoClaw Instead of OpenClaw

The harness layer is built on NanoClaw, a ~500-line TypeScript wrapper around the Anthropic SDK. The closest comparison is OpenClaw, a popular open-source framework for running AI agents. The design differs in one central dimension: surface area.

OpenClaw is full-featured and handles a lot of the plumbing automatically. NanoClaw deliberately stays small. At ~500 lines, you can audit the entire harness in an afternoon, understand every code path, and modify it for your environment without fighting framework conventions. That size constraint is itself a security property: with a minimal harness and a strict egress firewall, the attack surface is enumerable.

The permission model is split between two explicit tiers: admin-level operations (harness process — container lifecycle, volume mounts, network config, MCP server registration) and user-level agent operations (runs inside the container with minimal permissions). The agent can only take actions the harness exposes via MCP. There is no path for a model to escalate from user-level to admin through prompt manipulation, because the privilege boundary is enforced by the OS process model, not the application layer.

The tradeoff: you own more of the plumbing. SDK upgrades, tool permission changes, and new MCP server integrations all require editing the harness. For a team that wants deep customization and a clear security story, that's a feature. For a team that wants to stay on autopilot, OpenClaw is the better starting point.

## Security and Permissioning

Security was first-class from day one, not retrofitted:

- Network egress firewall. Containers have an allowlist-only outbound policy. Adding a domain requires an explicit config change and a live reload — the model can't silently reach arbitrary external endpoints.
- No secrets on disk. All credentials are stored encrypted in Google Secret Manager and auto-injected at session start. The model writes secrets via a dedicated MCP tool — never to a plaintext file.
- Per-user isolation. Each user's private workspace is inaccessible to other users and to agents in different channels. Information never crosses workspace boundaries.
- Least-privilege IAM. The GCP service account uses a custom role scoped to exactly the permissions needed, with an audit script to validate configuration drift.
- Tool permission tiers. Operators configure which tool calls require human approval. Destructive actions — database writes, deploys, deletes — require explicit confirmation. Read operations run freely.
- Hook-based automation. Automated behaviors are configured as hooks executed by the harness, not the model — so they can't be bypassed via prompt manipulation.
- Prompt injection defense. Content from web pages, emails, and cached external data is tagged as untrusted and treated as data, never instructions.

Permission modes run a spectrum: `auto` (model decides, high-stakes actions prompt the user), `acceptEdits` (file edits auto-approved, bash requires confirmation), `bypassPermissions` (everything runs without prompts — used only in fully automated scheduled tasks with no human in the loop). All hooks execute in the harness process, not in the container — so even a fully autonomous agent operating in bypassPermissions mode cannot suppress or rewrite them.

The egress firewall is implemented at the container network level using iptables rules applied when the container starts. The allowlist is read from a config file and can be reloaded live without restarting containers: the model can request a new domain by editing the config, but a reload MCP call is required to apply it — creating an observable, auditable step between request and effect rather than a silent background connection.

## Data Sources and Local Caching

The most impactful architectural decision was mirroring all major company data sources into local SQLite databases, synced on schedules from each source's API. Here's the full picture at our current scale:

- Slack — ~78,000 messages, 648MB. The full internal communication history.
- Notion — 15,000+ pages, 90MB. The entire company wiki, specs, and documents.
- CRM (Salesforce) — 38,000+ records: 3,000 accounts, 465 open deals, 5,000 leads, 6,000 contacts, 23,000 tasks.
- Meeting transcripts — 1,700 recorded meetings with 663,000 transcript entries spanning 16+ months.
- Google Calendar — 5,900 events across 21 calendars, categorized by meeting type.
- Codebase snapshots — key repos indexed at file-level granularity for code search.
- Domain documentation — technical specs, protocol docs, standards, indexed and searchable.
- Gmail — per-user via OAuth, with tiered permission scopes (read-only, draft creation, archive/label).

Syncs run on different schedules based on volatility: Slack messages every 30 minutes, Notion pages hourly, Salesforce records every 6 hours, calendar events daily. Each sync is incremental, tracking a high-water mark and pulling only new or modified records since the last run. This keeps sync duration short (seconds to low minutes) regardless of total corpus size.

All databases are opened with the `?immutable=1` URI parameter for agent reads. This disables WAL checkpoint and journal file checks, allowing fully concurrent reads across multiple containers without any locking overhead. Only the sync process holds a write connection. A typical agent container opens 10–12 SQLite databases simultaneously at session start; the immutable flag means none of them block each other or the sync writer.

## Semantic Search

All caches use SQLite's FTS5 (Full-Text Search version 5) extension, which builds inverted indexes over text columns. What this gives you:

- Phrase queries — "settlement finality" matches that exact phrase, not just documents containing both words in isolation.
- Prefix search — "settl*" matches settlement, settling, settler.
- Column-scoped queries — search only message body, not sender name; or only document title, not body.
- BM25 relevance ranking — results ranked by term frequency and inverse document frequency, the same algorithm used by traditional search engines.

A unified search script queries all caches simultaneously in parallel and merges ranked results across every source. Total latency across the full corpus is consistently under 100ms — no API calls, no rate limits, no per-query cost. The model is instructed to always search local caches first before ever claiming it doesn't have access to something.

Beyond text search, each cache exposes domain-specific structured queries: the CRM cache has pipeline (deal funnel view), account-summary (all activity for an account), and contacts-for commands. The calendar cache has upcoming, meetings-for (everyone's schedule with a given person), and meeting-type filters. These aren't just keyword search — they're normalized relational queries.

I'm deliberately not using vector embeddings for semantic similarity. FTS5 + BM25 has been sufficient for the retrieval tasks that come up in practice. The main gap is synonym and paraphrase matching, which matters occasionally but not often enough to justify maintaining a vector store. I'll add embeddings when the failure cases accumulate.

Under the hood, each cache uses stemming so that variant forms of a word ("settling", "settled", "settlement") all match the same query. The ranking algorithm is BM25, which weights results by term frequency and document rarity. Because scores aren't directly comparable across databases of different sizes, the unified search layer normalizes them before merging — with configurable weights per source so that, for example, an exact phrase match in a Notion doc ranks higher than a loose keyword hit in a Slack message.

## Knowledge Compilation

I implemented the Karpathy LLM knowledge base pattern for entity-level intelligence. The idea: instead of doing multi-source retrieval at query time (slow, expensive, context-heavy), a scheduled job pre-compiles all evidence about key entities into structured wiki articles.

Two phases: (1) Gather — pull every piece of evidence about an entity (an account, partner, deal) from CRM, Slack, docs, and calendar into structured JSON. Every message, every meeting, every activity. (2) Summarize — an agent reads that JSON and writes a concise, opinionated entity profile using a template. Query-time retrieval becomes a single-document read. Profiles stay fresh via scheduled re-compilation.

The key insight: pre-compilation shifts cost from query time (every conversation, many users) to batch time (once per schedule run), and produces a single coherent document instead of raw evidence scattered across four databases.

The gather phase produces a structured evidence object like this:

```json
{
  "entity": "Acme Corp",
  "crm": { "stage": "Negotiation", "arr": 120000, "close_date": "2026-06-30", "owner": "..." },
  "slack_messages": [
    { "ts": "1743200000.000000", "sender": "...", "channel": "#bd", "body": "..." }
  ],
  "meetings": [
    { "date": "2026-03-15", "participants": ["...", "..."], "summary": "..." }
  ],
  "docs": [
    { "title": "...", "url": "...", "excerpt": "..." }
  ]
}
```

The summarizer prompt is deliberately opinionated: it's told to surface risks, blockers, and momentum signals rather than just describe activity. The output template has fixed sections — relationship status, key contacts, open items, recommended next steps — so the profiles are structurally consistent and can be compared across entities. An agent writing "they went quiet after the last call" is more useful than an agent writing "last contact was 2026-03-15."

## Agentic Workflows

Beyond single-turn queries, the system supports several patterns for multi-step and parallel work:

- Agent swarms. A coordinator spawns named sub-agents that work in parallel. Each appears as a distinct Slack identity ("Researcher", "Coder", "Reviewer"). Sub-agents return results to the coordinator — never message the user directly.
- Pair programming loop. Coder implements, Reviewer critiques, Coder revises. Hard cap of three iterations, then ship. Prevents endless refinement.
- Pre-flight scripts. Every scheduled task can include a bash check that returns {wakeAgent: true/false}. The LLM only spins up if needed. A monitoring task running hourly only invokes the model when something actually changed.
- Heartbeat monitors. Recurring tasks diff state against a saved JSON snapshot and only alert on changes — useful for pipeline monitoring, PR queues, or any "notify me when X changes" pattern.

## Quality Metrics and Monitoring

An internal metrics API (no external auth, accessible from agent containers) exposes per-run cost breakdowns, daily cost history, agent run stats and error rates, active container counts, cache sync coverage and freshness, and task run history with failure detection.

Alert rules define when to fire vs. stay silent: urgent events always alert; low-priority items and out-of-hours events (10pm–8am) are suppressed. A platform that could generate constant noise needs explicit suppression rules to remain useful.

A use-case monitor tracks what the system is actually being used for across all conversations: which skill categories are invoked most, which queries hit the caches vs. fall back to the API, which tasks get corrected. This feeds a reinforcement loop. High-frequency use cases get dedicated skills and better prompts. Repeated corrections become durable memory entries. Queries that consistently miss in the local caches flag data sources worth adding. The system learns what it needs to be better at by watching itself work.

When a pattern appears consistently across multiple users — the same kind of query, the same multi-step workflow, the same correction — that's a signal to generalize it into a proper skill. A one-off prompt becomes a reusable template. A repeated workflow gets its own orchestration logic. The monitor surfaces these patterns; the skill system absorbs them. New users immediately benefit from what earlier users encountered and refined.

Closing the loop also means running UAT before shipping changes that affect how the system behaves for users. Prompt changes, new skills, modified memory rules — anything that touches the interaction model gets tested against representative queries before it goes live. The goal is catching regressions that unit tests won't find: cases where the system technically works but produces worse answers, or where a new skill conflicts with an existing one.

## Memory Model and Context Management

There are two distinct memory problems in a system like this, and they require different solutions. The first is in-session context: the LLM's active window fills up over a long conversation, degrading quality as irrelevant history crowds out recent signal. The second is cross-session persistence: the model starts each new session knowing nothing about what happened before.

For in-session context, the main countermeasure is treating the file system as external memory. Rather than holding intermediate results in the conversation thread, the agent writes them to files and references them by path. Tool output gets capped — extract what you need, discard the rest. Structured plans survive compaction better than freeform prose, because the plan file is always re-readable. Scheduled tasks always run in isolated context mode: no conversation history, all necessary context in the prompt. This eliminates an entire class of failures where a stale, hours-old conversation poisons a recurring job.

For cross-session persistence, the system uses a typed memory store: four categories (user profile, feedback, project context, external references), each stored as a markdown file with a one-line pointer in a central index. A separate FTS5-indexed search layer makes memories retrievable by keyword. The discipline that matters most: the model is explicitly told that saying "noted" without a file write means nothing was actually remembered. Without that rule, corrections evaporate.

## Self-Improvement

- Persistent memory. Four typed categories: user profile, feedback, project context, external references. Stored as markdown files with a searchable FTS5 index. The model is explicitly told: "noted" without a file write means nothing persisted.
- Feedback capture. Corrections and confirmed approaches are written as structured entries with a Why: and How to apply: line. Goal: the model is never corrected on the same thing twice. Each correction becomes a durable behavior change.
- Skills as config. Agent capabilities (prompts, workflows, domain knowledge) live in a Notion database, synced hourly to disk. Updating a skill means editing a Notion page — no deployment or code change.
- The skills database is private to employees. A company's skills repo isn't just prompts — it encodes how the business actually operates: the workflows people use, the judgment calls built into each skill, the domain knowledge that took years to accumulate. Publishing it would hand competitors a detailed map of your internal processes. Treating the skills repo as a proprietary asset, and building it deliberately, is one of the highest-leverage things a company can do with this kind of system. It compounds: every skill added makes the system more capable for everyone, and the gap between a well-maintained skills repo and a bare installation widens over time.
- Context rot prevention. Long sessions degrade as context fills with irrelevant history. Countermeasures: write intermediate results to files rather than hold in context, use isolated context mode for scheduled tasks, structured plans for multi-step work.

One of the stranger properties that emerges at this level of capability: the system can improve itself by reading other people's setups. An agent can look at how someone else configured their skills, notice a pattern that would work well here, and propose — or directly implement — the change. What's crazy about the current moment is that this loop is real. The system reaches a point where it understands its own scope well enough to keep extending it. You stop adding features to your AI assistant and start having it add features to itself.

## Who Can Build This — and What It Takes

Building something like this requires a surprisingly broad skill set in one person or a small team: sysadmin access to wire up integrations and manage infrastructure, enough coding ability to write skills and debug data pipelines, access to internal data sources (Slack, Notion, GitHub, CRM), a working understanding of what each team actually does, and the ongoing willingness to watch how people use the system and keep improving it. No single piece is especially hard — but you need all of them at once.

The goal also has to be scoped correctly. Not "enable the finance team to run their entire close process end-to-end," but "help a specific accountant speed up the part of their job where they personally create journal entries." Start with one person, one workflow, one bottleneck. Prove it works. Expand when the next bottleneck becomes obvious.

At 22 employees I can pull this off alone — I'm a super admin on every system, I understand the business context end-to-end, and I have the technical background to debug whatever breaks. At larger companies this probably needs a small dedicated team: someone to own the infrastructure, someone embedded in each business unit who understands the actual workflows, and someone responsible for maintaining and improving the system as it grows. The skills are real; they're just spread across multiple roles at scale.

## What I'd Do Differently

Build the web sanitizer on day one — wrapping all external content (web pages, emails, cached data) as untrusted is what actually stops prompt injection at the entry point, and retrofitting it means auditing every place the system reads outside data. The egress firewall is the network-layer counterpart and worth doing early too. Invest in the local cache layer earlier — the speed and cost difference versus live API calls at query time is larger than I expected, and the cross-source unified search turns out to be the most-used feature by far. Be more aggressive about the feedback memory system from the start — the compounding benefit is real but takes weeks to accumulate.

The biggest unlock wasn't any single feature. It was making the system's knowledge persistent and cumulative rather than starting from scratch each session. That's the shift from "an AI you query" to "an AI that knows your business."

> **📖** This is Part 1 of a two-part series. [Read Part 2: NanoClaw Architecture →](https://hub.bitsafe.finance/nanoclaw-architecture)
