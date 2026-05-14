---
title: How BitSafe Runs on Notion — Part 2: The Architecture
slug: nanoclaw-architecture
published: 2026-05-10
audience: Engineering / Founders / CTO
status: published
notion_id: 9b83cc35-79a8-4298-97d0-461e3458e2c9
---

Notion gives you infinite flexibility, which is why most workspaces become unusable. The constraint is the feature. Every database we have at BitSafe exists because the cost of *not* having a structured representation of that thing turned out to be higher than the cost of designing one.

This is a tour of the actual architecture. What we built, what we cut, and the principles behind every load-bearing decision.

## The Pillars → Projects → Tasks spine

Project work at BitSafe lives in a three-level hierarchy.

**Pillars** are the long-lived domains of the company. Sales. Marketing. Product. Engineering. Operations. Community & Developer Relations. Each is its own database, with its own home page, dashboards, Documents, SOPs, and Champion. A pillar is the unit of *accountability* — somebody owns the pillar, and everything underneath it.

**Projects** are time-bound, scoped efforts inside a pillar. The CBTC Incentive Program 2.0 is a project. The Q2 partner-launch campaign is a project. The Salesforce → Notion migration was a project. Projects have an owner, a status, a target date, and a set of Tasks rolling up.

**Tasks** are the unit of work. Every task is on a project (or, rarely, free-floating under a pillar). Every task has an owner, a status, and ideally a due date. The Tasks database is the single place where work-to-be-done lives, and it's the database that NanoClaw, the daily standup dashboard, and every team's "what's on" view all read from.

We resisted adding a fourth level. Sub-tasks exist as a self-relation on Tasks, but we don't model them as their own type. Every level you add multiplies the surface area the team has to keep clean.

Above the spine, **Rocks** (our quarterly company goals, in the EOS framework) plug in by relating to Pillars and Projects. Rocks aren't tracked in real time; they're a strategic layer that exists so the rest of the system can be checked against them.

## Documents is the gravitational center

If we had to keep one database, it would be Documents.

Documents holds every artifact that isn't a meeting, a project, or a task: Policies, SOPs, PRDs, Technical Specs, Proposals, Reports, Research, Memos, Guides, Reference, Analyses, Trial Reports. There are 17 Types currently, and the list grows when there's a real reason and not before.

Three properties make Documents work as the workspace's source of truth:

- **Responsible.** Every document has exactly one. It's the person who is accountable for whether this document is true. If they leave the company, this property gets reassigned before anything else.
- **Verification.** A built-in Notion property. Verified documents bubble up in search; verified documents are what the AI layer is told to prefer when it answers a question. Unverified documents are still useful — but the trust signal is explicit.
- **Status.** Drafting → In Review → Published → Archived. The default view filters out Archived, so old content doesn't pollute search.

The principle we drill in: **when in doubt, create a document.** Slack messages are not durable. DMs are not durable. Meeting transcripts are not durable. A document is. If a decision was important enough to make, it's important enough to write down — and the cost of writing it down is lower than the cost of someone re-asking the question in three weeks.

This is the property of Documents that makes the AI layer useful. Notion AI's retrieval is good. NanoClaw's local Notion cache (90MB, FTS5-indexed, ~15,000 pages) is good. Neither is good enough to compensate for content that doesn't exist. The retrieval problem is mostly a "did somebody write this down" problem.

## Meetings as structured output

Meetings is its own database, and every external/internal meeting we record automatically files there.

Fathom (our recorder) pipes the transcript and AI summary into a new Meetings row. A post-processing step extracts decisions and action items into the Tasks database, related back to the Meeting. The Companies and Contacts mentioned in the call get linked. The owner of the meeting gets a notification with a one-paragraph summary and a list of follow-ups.

The principle: **meetings produce structured output, not transcripts.** The transcript is there if you need it; you almost never do. What you need is the decisions, the owners, and the actions. That's what makes it onto the page.

This is also the database that makes meeting-prep automation possible. Our weekly KinCloud sync, the Wednesday marketing meeting, advisory calls — all of them have an SOP that runs against Notion's meeting history, recent CRM activity, and the agenda template, and produces a draft prep doc every week. The humans review it for ten minutes instead of writing it from scratch for an hour.

## Supporting databases that punch above their weight

A few smaller databases do disproportionate work.

**Updates** is a qualitative event log. When something happens to a Company or a Wallet that's worth remembering — a partner went quiet, a competitor showed up, a key person changed jobs — somebody (or some agent) writes an Update. Updates are short, dated, related to the entity they're about, and searchable. They're how we keep history without bloating the parent record.

**Event Log** is the quantitative cousin of Updates. Every state transition on an Opportunity (Stage moved, Amount changed, Owner reassigned) writes a row. This is what powers our pipeline-velocity dashboards and our "stalled deals" detection — without it, you'd be inferring state changes from comparing snapshots.

**Skills** holds the prompts and instructions that drive Notion's custom agents and (synced hourly) NanoClaw's container skills. Skills are documents — the agent capabilities are configured by editing a Notion page, not by deploying code. There are currently 74 skills across the system. New skills don't need a release cycle.

**Sales Routing Rules** is a one-table CRM lookup (region → owner). When an Opportunity is added to a Company, an n8n automation reads this table and assigns the right owner. To change routing, you edit the Notion table. No engineer required.

**Global Tags, Teams, People, Companies, Apps, Contacts, Canton Ecosystem Apps** — the directory layer. Master data, owned by Architects. Everything else relates into these. They're the reason we can join across the workspace at all.

## The dashboard layer

Notion shipped Dashboards in March 2026, and it changed what the architecture is for. Until that point, dashboards were a stack of linked database views with global filters that you had to set seven times. After it, a dashboard is a real first-class layout — multiple databases, cross-DB filters, KPI cards, charts, all responsive.

We rebuilt our home pages around this. Sales Home is one dashboard. The Daily Standup Dashboard is one dashboard. Each Pillar has a dashboard. The trick — and this is in the same family as Documents discipline — is that **dashboards come last**. You build the data first, you live in the data for a few weeks, you find the questions you actually ask, and *then* you build the dashboard. Dashboarding half-baked data ships a tool that nobody trusts.

## Schema discipline as a security model

We touched on this in Part 1; it's worth being concrete here.

The reason we can give a Slack-resident agent permission to create Companies, Opportunities, Apps, Contacts, and Tasks — and to update fields on existing records — is not that we trust the agent. It's that the agent works against a schema it cannot change.

It can't add a property. It can't rename a status option. It can't archive a database. The Architect tier holds those capabilities. Even if a prompt-injection attack convinced the agent to do something destructive, the worst it could do is create well-formed records inside a frozen schema. The blast radius is small and reversible.

This is the same logic, applied at a different layer, that NanoClaw uses with its dual-token Notion integration: a broad read-only token, and a narrow read+write token explicitly excluded from CRM and finance databases. The schema is the perimeter.

## What we cut

A short, useful list of things we built and then removed.

- **A separate Leads database.** Leads turned out to be Companies with an early-stage Engagement Status. Modeling them as their own object created a constant reconciliation problem ("did this Lead become a Company?"). We folded it back in.
- **Forecast Category, Node Operator, Custodians/Wallets, Source/Referred By on Opportunities.** The sales team didn't use them. The fields cluttered the capture flow and made the AI capture agent's job harder. Cut.
- **Per-Pillar Documents databases.** We tried it briefly. It made search across the workspace worse, and Champions ended up duplicating SOPs. One central Documents database with a Pillars relation is strictly better.
- **Inline databases inside meeting notes.** They didn't propagate sharing correctly to integrations and confused the AI layer's retrieval. We use related rows in the central Meetings DB instead.

## What we'd do differently

1. **Lock schemas before you build dashboards.** We didn't, the first time. Schema changes invalidate views. Every change cost us time we shouldn't have spent.
2. **Default to a Notion agent skill before adding a property.** Half the time, the thing you want is a derived view, not a new field. Properties are forever; skills aren't.
3. **Documents is the highest-leverage database.** Spend more time on it than on the CRM. The CRM is replaceable; the company's documented memory isn't.

---

> **📚** **How BitSafe Runs on Notion — series**
> Part 1: [Notion as the Company OS](https://hub.bitsafe.finance/how-bitsafe-runs-on-notion-part-1)
> Part 2: The Architecture *(you are here)*
> Part 3: [Agents, Automations, and the AI Layer](https://hub.bitsafe.finance/how-bitsafe-runs-on-notion-part-3)
> Part 4: [Replacing Salesforce with Notion](https://hub.bitsafe.finance/how-bitsafe-runs-on-notion-part-4)
>
