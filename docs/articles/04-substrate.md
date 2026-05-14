---
title: "The Substrate — Notion-as-OS, Data, Code, Knowledge, and Tools"
slug: 04-substrate
series: How BitSafe Runs on Notion
part: 4
published: 2026-05-14
audience: [App Developers, Trading Firms, Investors]
---

# The Substrate — Notion-as-OS, Data, Code, Knowledge, and Tools

If Part 3 showed the engine, Part 4 shows the substrate it runs on. Everything BitSafe's bots compose against — read, query, learn from, act on — lives in one of three layers: Notion (the operational substrate), local caches (the read-mirrors), or the engineered tool surface (the hands).

> Bots compose against Notion (substrate) + caches (mirrors) + tools (capabilities). The leverage isn't in the AI model — it's in what the AI can read and act on.

That sentence is the whole article. The rest is a case study: how a 14-person company built a substrate that bots can stand on, what's in it after six months of compounding, and what we'd do differently if we started over yesterday.

## Notion as the operational substrate

BitSafe doesn't use Notion as a wiki. We use Notion as the operating system.

The distinction matters because of how agents discover capability. A wiki is a place humans go to read. An operating system is a place where state lives, where verbs are defined, where any process — human or agent — can read, write, and coordinate. Every important entity in our company — capabilities, prose, customers, deals, contacts, third-party apps, tasks, research, and decisions — has a Notion database as its system of record. Bots discover what they can do by querying that database. Humans see the same rows in the same UI.

**Skills DB** (`c4c5db26-c776-4cea-9538-5619c05a94a1`). This is the canonical source for what any bot can do. Each row is a skill — a single capability with a name, a description, a trigger phrase, and a body. Rows are synced to disk hourly by `scripts/sync-skills-from-notion.py` into three locations (`/root/nanoclaw-skills/<name>/SKILL.md`, `container/skills/<name>/SKILL.md`, `marketing-ai-system/design_system/skills/<name>/SKILL.md`) where running agents can read them. Edits flow Notion → disk, never the other way around. On-disk edits are clobbered on the next sync. The cron is paired with a worktree-aware loader so an agent in a feature branch sees the same skill catalog as production.

**Documents DB**. Prose memory of the company. Every Notion page that codifies something — a strategy doc, a meeting prep template, a runbook, a customer-facing explainer — has a row in Documents with a Pillars relation and a status workflow (Draft / In Review / Live / Outdated / Archived). The article you're reading is a row in that database.

**Companies / Opportunities / Contacts / Apps DBs**. Post the 2026-05-13 Salesforce → Notion migration, this *is* the CRM. The migration replaced what had been our Salesforce instance: five downstream skills (`sales-leaderboard`, `investor-update`, `knowledge-compiler`, `commission-analysis`, `shortlist-from-corpus`) were repointed to read from Notion-resident company and opportunity caches; the ~130 MB Salesforce cache DB was scheduled for deletion; ongoing Salesforce cost dropped to zero. The Companies DB came across with 1,966 rows live during the cutover. Opportunities, Contacts, and Apps came across the same week. The most important thing about the migration is the thing it didn't require: no new "AI data layer." Notion was already that layer.

**Tasks DB** (`0018e560-d515-46b9-b205-b5a6e5e06c13`). Every significant task — engineering, marketing, research, ops — gets a row before work begins. Rows carry Tier, Priority, Pillar, and an SDLC checklist (verify, test, document, monitor, security, push). Agents executing a task tick the checkboxes as each phase completes. The day this article was drafted, seven new rows landed across the SF migration, a CRM autoflow fix, a reconciler refresh, a LegalBot ARQ item, and three others — each with its own auditable SDLC trail.

**ARQ DB** (Active Research Queue). Research items with priority (P1–P4), a circuit breaker (`research-queue-dispatch.py` enforces a daily ceiling of 10 to prevent runaway costs), and dispatch windows (P1/P2 every 15 min via cron; P3/P4 off-hours, 22:00–05:00 UTC). When an agent identifies a question that needs deep work — "what's our exposure to validator X" — it files an ARQ row instead of trying to answer in-stream. The queue is durable; the dispatcher is rate-limited; the work happens whether or not anyone is awake.

**Live Sales Collateral DB** (`2e3636dd-0ba5-80f0-8896-c8fe4e89d1e1`). The publishing pattern: a wrapper page in the DB carries metadata (Status, Type, Audience, Owner, Short Description, Last Reviewed); the body lives in a child page underneath. When the bot publishes a draft, the wrapper is created with `Status: In Review`, the markdown is converted to Notion blocks via `notion-writer/notion_blocks.js`, and a workspace-scoped URL is returned. Humans review in place. This article is being published through that same pipeline.

The thesis worth stating plainly: **no separate AI data layer because the company already has one.** Every team that's tried to build an "AI knowledge graph" alongside their CRM has discovered, six months in, that the AI knowledge graph and the CRM are the same object. We skipped that lesson by treating Notion as both from day one.

## Data connectors

Notion is the substrate. Everything else is a mirror.

BitSafe runs roughly 28 SQLite caches against non-Notion sources, each on its own sync cadence. The point of a cache is not redundancy. It's composition speed: an agent answering a sales question shouldn't pay a Slack API round-trip per query, and an agent compiling an investor update shouldn't be rate-limited by Google Calendar. The caches are read-only mirrors that let bots compose against external systems at SQLite latency.

The live inventory: `slack-cache` (every 10 min for hot channels, every 4 hours full), `notion-cache` and `notion-companies-cache` / `notion-contacts-cache` / `notion-opportunities-cache` / `notion-apps-cache` / `notion-event-logs-cache` (post-SF migration, the CRM mirrors), Notion-linked Drive files via `sync-notion-linked-files.py`, `pqs-cache` (Canton ledger via the Canton PQS endpoint), `fathom-cache` (meeting transcripts), `calendar-cache` (Google Calendar), `telegram-cache`, `canton-foundation-cache` (Canton ecosystem repos), `canton-docs-cache` (Playwright-rendered, because Canton's docs site is client-side rendered), `cips-cache` and `cip-discuss-cache` (Canton Improvement Proposals), `splice-cache`, `dlc-code-cache`, `cantex-docs-cache`, `cypherock-docs-cache`, `brale-docs-cache`, `nightly-docs-cache`, `ninety-docs-cache`, `cryptio-cache`, `qbo-cache`, `meet-cache`, `n8n-workflow-cache`, `temple-docs-cache`. Each cache lives at `data/<source>-cache/` on the host and mounts into containers at `/workspace/<source>-cache/`.

The architecture per cache is uniform: SQLite + FTS5 + (where embedding cost is justified) `sqlite-vec` for vector search. The uniformity is what makes the search layer composable — the `search-all` skill is a hybrid FTS5 + vector fusion across all caches with intent-keyed source selection, and adding a new source means producing a SQLite with the same FTS5 schema, not rewriting search.

**Sync cadence is engineered, not defaulted.** Hot Slack channels sync every 10 minutes because deals move there. The full Slack cache (incl. historical threads, bookmarks, group DMs) refreshes every 4 hours because the marginal value of fresher cold data doesn't justify the API cost. Notion CRM tables sync hourly because the CRM Capture Agent writes through Notion, and the agent population is reading. Canton Foundation repos sync nightly because they're large and they don't change every minute. Each cadence is a deliberate trade between staleness, API rate limits, and dollar cost.

**Memory-safe streaming is non-negotiable.** A cache sync that loads its corpus into memory before writing is fine — until it isn't. Today's lesson, courtesy of a 4 GB OOM in `bitsafe-gdrive-permissions/core/drive_api.py:426`: an accumulator pattern (`all_files = []; for page in pages: all_files.extend(page)`) that worked at 2,000 files crashed at 60,000. The fix is generators, not accumulators — yield each page as it's fetched, write it as it's processed, never hold the corpus in memory. Every new sync script in the fleet is now scaffolded from a generator template. We didn't learn this in theory; we learned it because a sync killed itself on a Sunday afternoon.

Composition over the caches happens through the `search-all` skill. An agent asking "what's the latest on Temple Digital" doesn't reach out to Slack, Notion, Fathom, and Calendar separately — it issues one hybrid query, the skill fuses FTS5 keyword hits with vector neighbors across the relevant caches, and the agent reasons over a unified result set. The intent layer — the keys in the cheat sheet that map "search company history" → `[notion-companies-cache, slack-cache, fathom-cache, calendar-cache]` — is what keeps the result set focused enough to actually be useful.

## Code ingestion

Data and code are different substrates and the distinction matters more than people expect.

A bot reads *data* to answer a query: who did we meet last week, what's the open pipeline, how many Slack mentions did Temple get. A bot reads *code* to learn a pattern: how does an existing skill structure its arguments, how does the Notion sync handle pagination, how does this internal app authenticate against the Canton ledger. The first is read-once-per-query; the second is read-once-per-author-cycle. They live in different parts of the substrate and they're consumed differently.

**Internal apps as readable corpora.** Four BitSafe-built apps are routinely cloned and indexed by sub-agents before they extend them: `cbtc-financials` (CBTC reserve accounting), `bitsafe-slack-admin` (Slack workspace admin tooling), `ccview-api` (Canton ledger view API), and `bitsafe-gdrive-permissions` (Drive permissions auditor). When an agent gets a task that touches one of these, the first action is to clone the repo, read the relevant module, and reason about the patch *before* generating code. This eliminates the entire class of "the model invented an API that doesn't exist" failures, because the model has the actual API in context.

**External libraries on demand.** Any `github.com` repo can be cloned (the egress firewall allows GitHub by default) and indexed. When Aki says "use the Daml SDK pattern for this," the agent clones `daml-lang/daml`, reads the relevant examples, and composes against them. The marginal cost of a clone is seconds; the marginal value of correctness is hours.

**Skill bootstrapping.** New skill authors — human or bot — read existing skills as exemplars. `cache-base/` is the canonical example for SQLite + FTS5 caches. `notion-writer/` is the canonical example for Notion publishing. `sync-notion-opportunities` is the canonical example for incremental sync from a Notion DB. This is why new skills land in hours, not weeks: the patterns are in the corpus, the corpus is mountable, and the bootstrapping cost is approximately one clone + one read.

Today's example is unusually concrete. The SF → Notion migration spawned three new sync scripts (`sync-notion-event-logs.py`, `sync-notion-companies.py`, plus the existing `sync-notion-opportunities.py`). Two of the three were drafted by sub-agents that read `scripts/sync-notion-linked-files.py` first as the canonical pattern. The migration shipped in a single afternoon because none of the sub-agents had to invent the sync pattern — they just adapted it. Code as exemplar, not just reference.

## Knowledge graph

Caches answer queries. The knowledge graph synthesizes understanding.

The `knowledge-compiler` skill compiles an entity graph nightly from the caches: companies, contacts, opportunities, Slack mentions, meeting attendees from Fathom, calendar invitees, partner relationships from internal Notion docs. The output is one Notion page per entity (company or contact), each with a synthesized summary, a fingerprint, a relationship list, and a links section. The graph isn't queried directly by humans much — it's queried by the daily standup generator, the investor update generator, and the BD digest, which fold it into prose.

The compiler was migrated today as part of the SF → Notion cutover. The new version reads the Notion Companies cache directly (no more Salesforce round-trip) and uses the new Notion Event Logs DB for stage history. The 1,966 companies that landed during the migration were populated live, with the compiler tracking the sync state in `data/knowledge-compiler-notion-state.json` so a restart wouldn't re-process rows it had already seen.

The abstraction worth naming: raw data is for queries; the knowledge graph is for *understanding*. An investor-update generator that pulls raw rows from twelve caches will produce a list. An investor-update generator that reads from a pre-compiled entity graph — where the "what changed about Temple Digital this month" question has already been answered offline — produces a narrative. The compiler is the place we pay the synthesis cost once, so every downstream consumer pays nothing.

## The tool surface (MCP)

The substrate is what the bots read. The tools are what they invoke.

BitSafe's bots run inside agent containers that expose a fixed surface of tools via the Model Context Protocol (MCP). The tool list is short and intentional: `send_message` (post to a channel), `store_secret` / `list_secrets` / `delete_secret` (manage per-user credentials), `list_agents` / `send_to_agent` / `check_agent_inbox` (the IPC bus that lets agents coordinate), `search-all` (the hybrid search across caches), `refresh_egress` (per-user egress allowlist refresh). Each tool is ~50 lines of TypeScript plus a Zod schema in `container/agent-runner/src/`, and each one is documented in the Skills DB so agents discover it the same way they discover any other capability.

Tool grants are scope-aware. Which tools an agent gets depends on its `group_folder` (the per-user or per-channel mount it runs against) and its role. A finance-channel agent gets QBO read access; a marketing-channel agent does not. A BD agent gets Salesforce-replacement Notion writes; a public-content agent gets read-only. The scope-wiring lives in `container-runner.ts` and the matching Notion routing-rules table — the table is canonical, the code reads from it.

Adding a new tool is approximately a day of work and produces a capability available to every container thereafter. The unit cost matters because it's what determines how many tools we have. A bot fleet with five tools is a different animal from a bot fleet with thirty. We're closer to thirty.

## Secrets as tools

Credentials are a substrate too, and the design choice that matters is who can *use* them, not just who can *read* them.

Google Secret Manager (project `ai-bots-488013`) is the canonical store. Per-user secrets follow the naming convention `nanoclaw-{userId}-{secretName}` with labels (`user={userId}`, `managed-by=nanoclaw`) so a fleet-wide audit is one filtered list call. A custom IAM role (`nanoclawSecretsManager`) bound to a single service account (`nanoclaw-meet@ai-bots-488013.iam.gserviceaccount.com`) carries only the seven permissions the code actually uses; nothing more.

The injection path: `container-runner` fetches all of a user's secrets at container spawn, passes them via stdin, and `agent-runner` writes them to `/workspace/user/.secrets/` with mode `0o600` (a daily audit cron at 04:23 UTC verifies this and pings admin if any file regresses). Agents call `store_secret` / `list_secrets` / `delete_secret` over the IPC bus, which forwards to the host, which writes through to GSM. Storing a secret writes to the local filesystem immediately *and* persists to GSM for next session — no restart needed.

Custom secret types trigger type-aware injection. `github-pat` auto-sets `GH_TOKEN` and writes `.git-credentials`. `gpg-key` imports into the user's GPG keyring and configures `git commit.gpgSign=true`. `vercel-token` exposes itself to the Vercel CLI. The type is inferred from the name (`*gpg*key*` → `gpg-key`, `github-pat*` → `github-pat`), so the storage step is uniform but the consumption step is correct.

Today's example: a fresh GitHub PAT for the `bitsafe-ai-docs` repo was provisioned through this exact path. Bootstrap cost was one `gcloud secrets create` call; this article was published using that PAT minutes later.

## Closing

A bot fleet is only as smart as what it can read and only as useful as what it can do. The model — Opus 4.7, Sonnet, Haiku, whatever ships next — is interchangeable on a 12-month horizon. The substrate is not. Notion, the 28 caches, the read-on-demand code corpus, the synthesized knowledge graph, the MCP tool surface, and Google Secret Manager are the things our bots are actually composing against. Replacing the model is a routing-table edit. Replacing the substrate would take a year.

> The AI is just the surface. The substrate is the strength.
