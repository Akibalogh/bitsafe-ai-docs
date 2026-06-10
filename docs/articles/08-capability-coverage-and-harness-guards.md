---
title: "Capability Coverage & Harness Guards — Why the Model Shouldn't Have to Remember What It Can Do"
slug: 08-capability-coverage-and-harness-guards
series: How BitSafe Runs on Notion
part: 8
published: 2026-06-10
audience: [App Developers, Trading Firms, Investors]
---

# Capability Coverage & Harness Guards — Why the Model Shouldn't Have to Remember What It Can Do

This is Part 8 of BitSafe's NanoClaw case study series. Part 7 was about catching what you can't prevent — surfacing the failures of an autonomous system to a human who can act. Part 8 is about a quieter failure that doesn't trip any alarm: the system *has* a capability, and doesn't use it. The skill exists. The data source is indexed. The tool is wired. And the agent answers "I can't do that," or worse, answers from a number it half-remembers from three weeks ago.

We call this **capability-blindness**, and it turned out to be the dominant failure mode once the system grew past a few dozen skills. Everything below is the set of patterns we landed to fight it — plus two adjacent lessons (guards over memos, and the ephemeral console) that come from the same root principle.

> The less the model has to hold in its head, the less brittle the system is. Decentralize, and force tool-use at the point of need.

## The capability-blindness problem

An agent system that does one thing can rely on the model knowing how to do that one thing. An agent system with hundreds of skills, dozens of indexed data sources, and a growing MCP surface cannot. The naive design — list every capability in the system prompt and trust the model to recall the right one — fails in three compounding ways:

1. **The list is too long to fit.** Past a certain size, "here is everything you can do" doesn't fit in the budget you're willing to spend on every single turn. So you trim it. The moment you trim it, the model is blind to whatever you trimmed.
2. **Recall is probabilistic.** Even when a capability *is* in context, the model doesn't reliably reach for it. It pattern-matches to "I'll write a quick script" instead of "there's a skill for this," because writing a script is the more common shape in its training. The capability exists and the model rolls its own anyway — slower, buggier, and inconsistent with how the rest of the system does that job.
3. **Memorized facts go stale.** This is the subtlest one. If the system prompt says "concurrency is 10" and the real config is 15, the model will confidently quote 10. The number was true when someone wrote it down. It is a lie now. A system that hard-codes its own facts into the prompt is a system that lies with increasing confidence as it ages.

The robust answer to all three is the same: **don't make the model remember. Make it discover.**

## Discovery, not memorization

The fix has four moving parts, and the design intent of each is to move a fact *out* of the model's head and into a place that's queried fresh.

**An intent-indexed catalog.** Instead of a flat dump of every skill, the catalog is keyed by *intent* — "writing to the wiki," "searching across sources," "posting a status update" — and the agent is instructed to consult it at the point of need, not to memorize it. The entry for each intent points at the one right way to do that job. This collapses problem (2): when the agent is about to write to the wiki, the catalog says "use the wiki-writer, here's how," and the model reaches for the tool instead of reinventing it. The catalog is small enough to consult cheaply and complete enough to be authoritative.

**Auto-discovered data sources.** The list of "what can I query" is not hand-maintained in a prompt. It's derived at runtime from what actually exists — the indexes that are present, the caches that are populated, the MCP servers that are reachable. A data source added last week shows up because it's *there*, not because someone remembered to add a sentence about it to the prompt. The corollary: a data source that quietly broke shows up as broken, instead of being silently claimed as available because the prompt still mentions it.

**An MCP surface, forced at the point of need.** Tools live behind a uniform protocol surface rather than as prose instructions. The agent is pushed to enumerate and call them rather than to recall whether they exist. "Forced at point of need" is the operative phrase: the catalog and the tool surface are consulted *when the agent is about to act*, not loaded once at the top and hoped-to-be-remembered fifty turns later.

The principle underneath: a capability the model has to remember is a capability the system can lose. A capability the model discovers is one the system keeps as long as it's actually wired up.

## The session-start self-test

Discovery handles "what can I do." A second mechanism handles "can I actually do it right now." At the start of a working session, the system probes each *category* of capability for reachability — can it read the knowledge base, reach the search index, hit the calendar, call the deploy surface — and reports the result.

This matters because the gap between "the capability is configured" and "the capability works right now" is where a lot of wasted effort lives. An agent that spends ten turns trying to use a data source whose auth token expired this morning is worse than an agent that knew, at turn zero, that the source was down and routed around it. The self-test turns a slow, mid-task discovery of brokenness into a fast, up-front one. It's the same instinct as a preflight checklist: you don't find out the instruments are dead after you've taken off.

The self-test is per *category*, not per individual capability — probing all of them on every session start would be too expensive, and category-level reachability ("can I reach the search layer at all") catches the failures that matter. When a category comes back unreachable, that's a signal worth surfacing, exactly the way Part 7's monitors surface a broken cron.

## The drift-detector: query facts, don't memorize them

The third mechanism closes the loop on problem (3) — stale memorized facts. The rule is blunt: **anything that changes — a rate, a count, a config value, a balance, a status — is queried live at the moment it's needed, never recited from memory.**

A memorized number is a landmine with a delay fuse. It was accurate when written. Every day after, the probability that it's still accurate decays, and the system has no way of knowing it's decayed because the number sits there looking just as authoritative as the day it was true. The drift-detector pattern is the refusal to trust that look: when an agent is about to quote a live fact, it goes and gets the current value, and if it can't, it says so rather than falling back to a remembered one.

This is the inverse of the institutional-memory pattern from Part 5. *Settled* knowledge — how we work, what a rule means, why a decision was made — belongs in propositional memory, written down and heeded. *Live* facts — numbers that move — belong nowhere near memory; they belong at the end of a query. The skill is telling the two apart. "We don't talk to customers" is a durable rule; keep it in memory. "Concurrency is set to N" is a live config; query it. Writing the second kind into memory is how a system starts confidently misinforming the people who rely on it.

> Settled knowledge goes in memory. Live facts go at the end of a query. Confusing the two is how a system learns to lie politely.

## Harness guards over memos

The capability work has a sibling lesson, and it comes from watching which corrections actually stuck.

When the system did the wrong thing — reached for the wrong tool, took an action it shouldn't have — the first instinct was always to write it down. A memory file, a line in the operating doc, a note in the relevant skill: *don't do X.* And for a class of mistakes, that works: a written rule, loaded at session start and heeded, is exactly the propositional-memory loop that makes the system get less wrong over time.

But some rules kept getting violated *despite* the memo. We'd write "don't do X," and weeks later something did X anyway — a different agent, a different code path, the same mistake. The memo taught; it didn't enforce. And the thing about a probabilistic actor is that "taught, but not enforced" eventually means "did it anyway."

The pattern we landed on: **when a behavioral rule keeps getting violated, stop adding documentation and move enforcement into the harness.** A pre-action guard that intercepts the wrong move at the moment it's attempted does what no memo can — it makes the wrong action *impossible*, not merely *discouraged*. Memos are for teaching humans and steering judgment. Guards are for the rules that must hold every time regardless of which actor is at the keyboard or how the model is feeling that turn.

The decision rule is simple. A rule that's been violated once after being written down is a teaching problem — maybe the memo was unclear. A rule that's been violated *repeatedly* despite being written down is an enforcement problem, and the fix is a guard in the harness, not a louder memo. The cost of a guard is real (you have to build it, and an over-eager guard blocks legitimate work), so you spend it on the rules that have earned it by recurring.

> Memos teach. Guards enforce. When a rule keeps breaking, you don't need a clearer memo — you need a harness that won't let the rule break.

## The console is ephemeral

The third lesson is about *where work lives* while it's being done, and it's the most operationally important of the three.

The interactive console an operator drives — the session where a human is steering the agent — is disposable. It can be killed, it can crash, the machine can reboot. Treat it as if it could disappear at any moment, because it can. The test for whether something is safe to leave in the console is one question:

> If this session were killed right now, would anything be lost?

If the answer is yes, that thing is in the wrong place. The fix is to *decentralize* it — to push it out of the ephemeral session and into a durable store before the session ends:

- **Code → version control.** A commit (or a pushed branch) survives the session; an uncommitted edit does not.
- **Documents, reports, findings → a durable store.** A written page in the workspace survives; a paragraph that only exists in the conversation does not.
- **Tasks → a queue.** A filed task survives; a "remind me to do this later" said to the agent does not.
- **Scheduled or long-running work → cron / a supervised service.** A scheduled job survives a console death; a background process started *inside* the console dies with it.

That last one is the trap that taught us the rule. A recurring data pull had been set up as a background process living inside an interactive session. It worked — right up until that session was killed, at which point the recurring job simply stopped, silently, and a downstream alert quietly lost data with no error anywhere. Nothing was broken in a way a monitor could see; the work just stopped happening because the place it lived had vanished. Recurring or durable work belongs in cron or a managed service, never as a child of a session that's allowed to die.

What's *allowed* to live in the console is the work of the current turn: read the input, decide, act, report, and — critically — make sure the durable artifacts (the commit, the page, the filed task, the cron entry) exist before the turn ends. Swarms of sub-agents are fine *because they commit their work to version control* — the commit is the durable artifact, not the agent. The session is a workspace, not a vault. Anything you'd be sad to lose has to be written somewhere that outlives the workspace.

## The common root

These three patterns — discovery over memorization, guards over memos, the ephemeral console — are the same principle wearing three coats.

A capability you have to *remember* is one the system can lose. A fact you *memorize* goes stale and misleads. A rule you only *document* gets violated anyway. Work that lives *only in the session* dies with it. In every case, the brittleness comes from trusting a single, fragile, in-the-moment place — the model's recall, the prompt's stale text, the operator's discipline, the live session — to hold something the system depends on.

The robust move is always to push that something *out* into a place that's queried fresh, enforced mechanically, or persisted durably: a catalog the agent consults at point of need, a live query instead of a memorized number, a harness guard instead of a memo, a durable store instead of a session. The less the system keeps in any single brittle place, the more of it survives the inevitable moment that place fails.

It's the same lesson Part 7 ended on, generalized one more level. There, the point was that a check is only as good as its surfacing. Here, the point is that a capability is only as good as the system's ability to *find and trust* it under real conditions — not under the conditions that held the day someone wrote the prompt.

---

**Related reading inside this case study:**
- [Part 2: Architecture](02-architecture.md) — the schema-as-perimeter idea is the structural cousin of harness guards
- [Part 3: The Autonomous Engine](03-autonomous-engine.md) — the loops and CI/CD that the ephemeral-console rule keeps honest
- [Part 5: Working with NanoClaw](05-working-with-nanoclaw.md) — propositional memory for settled knowledge, the counterpart to querying live facts
- [Part 7: Monitors & Alerts](07-monitors-and-alerts.md) — surfacing what you can't prevent, the sibling discipline to discovering what you can do
