---
title: "Cost Discipline — Why the Bill Grew, What We Caught, How to Catch It Sooner"
slug: 06-cost-discipline
series: How BitSafe Runs on Notion
part: 6
published: 2026-05-17
audience: [App Developers, Trading Firms, Investors]
---

# Cost Discipline — Why the Bill Grew, What We Caught, How to Catch It Sooner

This is Part 6 of BitSafe's NanoClaw case study series. Parts 1-5 covered architecture, autonomy, substrate, and the daily working pattern. Part 6 is a postmortem-as-playbook: how the Anthropic bill grew past plan in May 2026, what we found when we went looking, and the layer of cost vigilance we built to make sure the same blind spots don't return.

The headline numbers, before we start. BitSafe runs NanoClaw on an Anthropic Tier 4 org with a $15,000/month spend cap. On May 17 the month-to-date was $9,941 with two weeks left — projecting to ~$18,000 at the run rate, over cap. In a single Sunday afternoon we found and shipped seventeen separate cost levers — every one a real bug or a real over-routing decision. The arithmetic, conservatively: ~$4,500/month of savings now active in production, with a Haiku-triage layer in flight worth another ~$400/month. None of the fixes were dramatic; the model is the same Claude Opus 4.7 we've been using all year. The leverage was in observability — the moment we could see *where the money was going*, the fixes wrote themselves.

## What we knew vs. what we couldn't see

The starting state was deceptively comfortable. We had a daily Anthropic-cost monitor (`scripts/daily-anthropic-cost-monitor.py`) that posted MTD totals + cache-hit rates to admin chat at 08:00 UTC. The cache hit rate was a healthy 99.42%. Daily totals looked stable. The model split looked reasonable: Sonnet for most work, Opus for hard reasoning. Nothing was screaming.

But three classes of cost were invisible:

**(1) Per-spawn cost attribution.** The cost-telemetry log at `data/anthropic-cost-telemetry.jsonl` recorded every API call's input/output/cache tokens — but the `container_src_ip` field for every spawn was `127.0.0.1` (the credential-proxy's local IP). When `cost-by-skill-report.py` tried to attribute spend to a skill or group, it got 0% matches. Every dollar was tagged "unknown:unknown." We had a sum, but not a breakdown.

**(2) Tier-aware pricing.** Claude Opus 4.7 has two pricing tiers: standard up to 200K context ($15 input / $75 output per 1M tokens), and "extended" 200K-1M context ($30 / $112.50 — 2× input, 1.5× output). Our MTD tracker applied the standard pricing to *every* row in the Anthropic CSV export, regardless of which tier billed. For each 200K-1M row, we were undercounting by 2×. Over a month, the gap was ~$2,950 of silent under-reporting.

**(3) Per-channel spawn volume.** Each container spawn cost $0.05-$0.30 on average, well below any alarm threshold. But if a scheduled task fired in an archived Slack channel every 5 minutes for four days, the individual cost was invisible while the aggregate was real money. We had no "spawns per `chat_jid`" tracker.

These three gaps shared a property: they didn't cause loud failures. They caused *silent over-spending*. The system kept working; the bill kept growing.

## The seventeen levers

The investigation started with one question — *where did the last $5,000 go?* — and unrolled into seventeen distinct findings. We grouped them by where the cost was hiding.

### Lever 1: A long-running Claude Code session on the 1M-context tier

The biggest single discovery was personal. Aki — BitSafe's CEO and the heaviest individual user — kept a Claude Code session running in tmux on the host for hours at a time, asking architecture and strategy questions. The CC binary defaulted to the model identifier `claude-opus-4-7[1m]`, which engages the 200K-1M extended-context tier *whether or not the conversation actually exceeded 200K tokens*. The session paid the 2× input premium on every turn.

The fix was a one-line edit to `/root/.claude/settings.json`:

```json
{
  "model": "claude-opus-4-7",
  ...
}
```

Dropping the `[1m]` suffix returns to standard pricing. Cache-read tokens (the dominant cost category for long-running sessions) move from $3.00/M to $1.50/M — a clean 50% reduction. Three days of telemetry showed Aki's session burned $3,744 on extended-context Opus; the same usage pattern at standard tier projects to ~$4,200/week saved.

The wider lesson: *the most expensive part of the bill was a single config-file default*. We had no observability into which model variant was being used at the per-session level until the postmortem.

### Levers 2-3: Tier pricing fix + 200K-1M throttle calibration

Once we knew the 1M tier was the silent multiplier, we fixed our MTD tracker so the auto-throttle works. `scripts/sync-anthropic-mtd-from-csvs.py` now reads each CSV row's `context_window` column and dispatches to a per-tier pricing table:

```python
PRICING_PER_1M = {
    "opus":   {"standard": {"input": 15.0, "output": 75.0},
               "extended": {"input": 30.0, "output": 112.5}},
    "sonnet": {"standard": {"input":  3.0, "output": 15.0},
               "extended": {"input":  6.0, "output": 22.5}},
    "haiku":  {"standard": {"input":  0.8, "output":  4.0},
               "extended": {"input":  0.8, "output":  4.0}},
}
```

Recomputing May 2026 against the corrected table moved MTD from $11,137 → $14,092 — a 26.5% revision. Crucially, the auto-throttle's threshold checks (`MTD > 90% of target`) now fire on the *real* spend, not the under-counted version.

### Lever 4: The skill-detected → Opus shortcut

The model router (`src/model-router.ts`) classifies each inbound Slack message by complexity score (Gemini 2.5 Flash Lite, scoring 0.0-1.0) and routes to Haiku, Sonnet, or Opus based on boundary constants. But the router also had a *shortcut*: if the inbound message matched a known skill keyword (`commission`, `notion`, `daily-standup`, etc.), it bypassed the score and went straight to Opus. The rationale was reasonable when introduced ("skills imply complex reasoning"); the reality was that 458 of every 500 routing decisions hit this shortcut.

The shortcut sent everything to Opus. *Including* one-line requests like "post today's standup" or "search for X in Notion" — work Sonnet handles capably for one-fifth the cost.

The fix had two parts:

1. **Default the `skill_detected` shortcut to Sonnet instead of Opus.** Skills that genuinely need Opus (high-stakes monetary analysis, contract redlining, board-memo drafting, architecture diagramming) opt in via an explicit allowlist:

   ```ts
   const SKILL_OPUS_ALLOWLIST = new Set([
     'commission-arbitration',
     'commission-analysis',
     'architecture-diagram',
     'legal-redline',
     'investor-update',
     'design-agent',
     'cross-source-compare',
     'premortem',
     'six-sigma',
   ]);
   ```

   The allowlist is runtime-overridable via `NANOCLAW_SKILL_OPUS_ALLOWLIST` so we can tune without a rebuild.

2. **Layer in admin-deep-analysis tilt.** Skill-default-Sonnet would drop too aggressively if a human admin (Aki, Jesse, Kadeem) is asking a genuinely deep question. We added four additive score bonuses:

   | Signal | Bonus |
   |---|---|
   | Admin sender (Aki / Jesse / Kadeem) | +0.05 |
   | Deep-reasoning verb match (`evaluate`, `decide`, `tradeoff`, `strategy`, `should we`) | +0.03 |
   | Counterfactual phrasing (`what if`, `had we`, `implications of`) | +0.02 |
   | Long open-ended question (>30 words, no enumeration, has `?`) | +0.02 |

   So an admin asking *"what's the implications of moving to a token-launch model — should we tradeoff X for Y?"* clears the bonus chain to ~0.12 and reaches Opus. The same admin asking *"show me dashboard"* sits at -0.05 and lands on Haiku. Non-admin partners are hard-capped at Sonnet regardless of bonuses unless they explicitly write `use opus`.

The conservative projection on these two changes alone: $1,000-2,000/month, with the upper bound likely as Phase 2 (below) shifts more spawns to Haiku.

### Levers 5-7: Lower-and-narrower boundary defaults, A/B logging

The boundary constants themselves were too tight. With `HAIKU_BOUNDARY=0.05` and `OPUS_BOUNDARY=0.07`, only the lowest-complexity messages reached Haiku. In production we observed: 67% of scoring-bypass spawns to Haiku, 19% to Sonnet, 14% to Opus.

Widening the bands to `HAIKU_BOUNDARY=0.08` and `OPUS_BOUNDARY=0.12` re-routes the borderline messages: ~90% to Haiku, ~10% to Sonnet, 0% straight-to-Opus from the boundary path. We also wired an A/B log (`data/model-router-ab.jsonl`) that records both the new tier and the tier that would have been chosen with the old boundaries — so after a week we can measure the real cost shift, not just the projection.

Boundary tightening alone projects $700-1,000/month. Combined with the skill-allowlist change, the model split should move from "59% Opus / 39% Sonnet / 2% Haiku" toward "20% Opus / 60% Sonnet / 20% Haiku" — closer to the price-weighted distribution the work actually deserves.

### Lever 8: The cache-creation TTL gap

Anthropic's prompt cache has a 5-minute ephemeral TTL by default in the Claude Agent SDK's `preset: 'claude_code'` configuration. If a scheduled task fires every 15 minutes (e.g., the pre-meeting-brief reminder), the cache expires *between every fire* — and every fire pays full cache-creation cost (1.25× input rate) instead of cache-read cost (0.10× input rate).

This was almost the entire 0.58% cache miss. The math: ~$240/week of cache-creation cost concentrated in `slack_main` task threads, projecting to ~$1,040/month. A switch from 5-minute to 1-hour TTL would cut roughly 54% of that — ~$560/month. The Agent SDK doesn't expose `cacheTtl` today; the fix is either (a) an upstream SDK PR or (b) a manual `/v1/messages` bypass for scheduled-task spawns. Either is a real engineering project, so we shipped the *watchdog* first (`scripts/cache-creation-audit.py`) and parked the underlying fix as a follow-up. The watchdog runs daily at 06:00 UTC and pings admin when wasteful spawns exceed 5 in the trailing 24h.

The wider lesson: knowing where waste lives is more valuable than fixing it immediately, *as long as the measurement comes first*.

### Lever 9: The runaway in an archived channel

One Slack channel — `C0AMQGEJX45`, formerly `#marketing-ai-design`, now archived with 0 members — kept firing scheduled tasks at `*/5 * * * *`. Over four days the channel accrued 1,099 container spawns. Each spawn short-circuited at the pre-flight check (`wakeAgent: false` because the channel's Notion DB had no "Ready for agent" rows), so the per-spawn cost was small. But the cumulative warm-pool churn was real, and the spawn count was hidden because no individual spawn breached the $3 alert threshold.

The fix had two parts. First, we paused the scheduled tasks targeting the dead channel — a one-time database update against `store/messages.db`. Second, we built `scripts/runaway-spawn-detector.py` to catch the next one before anyone notices. It runs daily at 07:00 UTC and flags any `chat_jid` with more than 50 spawns in 24 hours, then cross-references each flagged `chat_jid` against the live Slack API: archived channel? zero members? dead chat? The script's first dry run caught the same `C0AMQGEJX45` pattern *and* a healthy 102-spawn pattern in Aki's DM (not flagged as runaway, just noted).

### Levers 10-13: Real-time + scheduled cost alarms

Once we knew what *had* gone wrong, we built the alarm layer for the next time.

- **Per-spawn cost alert** (`src/per-spawn-cost-alert.ts`): the credential proxy now logs each spawn's total cost on container close, using the Agent SDK's authoritative `lastMetrics.total_cost_usd` field. Spawns ≥$3 fire `ping-admin.sh --severity warning`; ≥$10 fire `critical`. Per-group cooldown 30 min. Critical bypasses cooldown.

- **Hourly cost-tick** (`scripts/hourly-cost-tick.py`): every hour at `:15`, compares the last hour's spend to the trailing 24h average. Spike >2.5× with last-hour spend >$5 fires warning; >5× with last-hour >$20 fires critical. Cooldowns 90 min per severity. Replayed against the May 11/12/13 spike days, the tick would have fired `critical` at 12:00 UTC each day — same-hour visibility instead of next-morning at 08:00.

- **Top-N spawn digest** (`scripts/top-cost-spawns-digest.py`): daily at 07:30 UTC, posts a 4-6 line summary of the top-cost spawns of the previous 24h to admin chat, with a link to the full markdown log. Catches the long tail of $1-2 spawns that the per-spawn alert misses but that aggregate to real money.

- **Cost vigilance score** (extension to `daily-anthropic-cost-monitor.py`): a 0-100 composite emitted in the existing 08:00 dashboard. Components: cache hit %, MTD pacing vs target, spawns >$3 in 24h, runaway `chat_jid` count, Opus share of total spend. The score is intentionally simple — five buckets of 30/25/20/15/10 — so deterioration in any one shows up as a noticeable drop in the headline number. A "controls working, spend overshot" snapshot reads 40/100, not 0; perfect reads 100.

### Levers 14-17: Per-spawn context shrinkage

The other half of the cost equation is *what each spawn pays for*. Auditing per-spawn input token distribution surfaced numbers that made the team uncomfortable.

| Metric | Tokens |
|---|---|
| Median per spawn | 424K |
| P95 | 5.5M |
| P99 | 7.5M |
| Max | 8.8M |

74% of spawns were >200K total billable context (input + cache_read + cache_creation), and those spawns ate 93% of the weekly cost. Zero spawns under 50K — there was a hard floor of ~100K from the global system prompt + skill files + tool definitions before *any* user content was added. The bloat was a Sonnet-volume problem, not an Opus problem (Sonnet median 426K × 10× the spawn count overwhelmed Opus's larger-per-spawn footprint).

The two shrinkages we wired in:

- **Tiered `globalClaudeMd` loader** (`container/agent-runner/src/global-claudemd-loader.ts`): splits `CLAUDE.md` into an *always-loaded core* (philosophy, top working patterns, must-know rules — ~6,188 tokens) versus a *heavy section* (troubleshooting, full key-files table, runbooks — adds ~4,717 tokens for `debug`/`setup`/`incident-class` skills only). Light-weight skills (`search-all`, `daily-standup`, `notion-writer`) get the core only.

- **Tiered skills cheatsheet**: the canonical `SKILLS_CHEATSHEET.md` is 4,889 tokens (every container loads it at boot). The top-15 most-used skills (measured: `team-digest`, `cbtc-financials`, `marketing-abm`, `knowledge-compiler`, etc.) account for 40.2% of all skill reads. A tiered top section captures those at 1,846 tokens; the full file is preserved as `SKILLS_CHEATSHEET_FULL.md` for fallback when an agent doesn't find what it needs in the top.

Combined per-spawn savings, after wire-in and host-side mount: ~7,700 fewer input tokens per non-heavy spawn. At ~3,000 spawns/week, ~23M fewer billable tokens/week.

## The Haiku triage layer — a small, smart model as the router

The most architecturally interesting lever shipped today isn't a cron or a watchdog — it's the Haiku triage layer. Worth a section of its own because the pattern generalizes beyond cost.

The orthodoxy in agent systems is that the strongest model serves every request: Opus or its peers at the top of the stack, gated only by the user typing the explicit "use opus" / "use haiku" override. The result is that *every* inbound message — from `"hi"` to *"evaluate the tradeoff between a token-launch model and a subscription model given our current cash position"* — pays for the same expensive container spawn. Most messages do not deserve that.

The first attempt at fixing this was deterministic shortcuts (Phase 1): seven regex patterns intercepting the absolute-cheapest cases (`/help`, single-word greetings, plain `thanks`) before any LLM is involved. That works at $0 marginal cost, but Aki was right to push back: regex is brittle. *"hey @NanoClaw thanks but actually can you also check X"* matches the `thanks` regex, reacts 👍, and silently drops the actual request. Typos, phrasing variants, and mixed intent all leak through.

The Phase 2 answer was to put Haiku itself in the routing seat. Haiku 4.5 is roughly 1/100th the cost of a Sonnet spawn and 1/500th of an Opus spawn. At those rates, it's cheap enough to be the *router and the answerer*, not just a classifier.

The runtime flow:

```
inbound msg
  → bot-mute / access-control / per-thread rate-limit         (existing)
  → deterministic shortcuts (Phase 1, 0-cost — keep for the unambiguous cases)
  → Haiku triage (Phase 2)                              [~$0.0006/call, measured]
      ├── direct_answer:  Haiku writes the reply itself, no container spawn
      ├── cache_lookup:   host-side script reads a local cache (calendar, Tasks DB,
      │                    slack-cache, etc.), formats the reply, no container spawn
      └── full_agent:     fall through to container — model-router picks Sonnet/Opus
```

The classifier prompt is intentionally narrow. Haiku gets a 600-token system prompt enumerating the three intents, the recognized cache-lookup targets (`next_meeting`, `today_tasks`, `slack_thread_summary`, etc.), and a few hard rules:

- *"If the message asks you to DO something (send, post, write, file, schedule, delete, modify), intent = full_agent."*
- *"If the message contains the phrase 'use opus', intent = full_agent."*
- *"If unsure, intent = full_agent (better to over-spawn than under-answer)."*

Response shape is forced JSON: `{intent, response?, target?, confidence: 0.0-1.0}`. Below a 0.85 confidence threshold the message falls through to a full container spawn. Five hard guards short-circuit *before* the Haiku call even fires: admin sender (Aki — his messages are complex by default and bypass triage entirely), bot senders (no cross-talk), messages over 200 characters, messages matching tool-requiring verbs (`send|post|write|file|schedule|delete|modify`), and MPIM channels.

Three properties make this work as a cost lever specifically:

**Haiku is cheap enough to be wrong.** A misclassification costs us $0.0006 plus a follow-up container spawn (~$0.10). At those numbers, the "if unsure, full_agent" rule has near-zero downside — over-spawning is much cheaper than under-answering. Compare to a classifier that costs the same as the spawn it's replacing: there's no asymmetry, the lever evaporates.

**The cache-lookup intent unlocks a *new* response class.** "What's my next meeting?", "what's on my Tasks DB for today?", "summarize this thread" — these are all questions whose answer already exists in a local cache. A full container spawn pays an Opus or Sonnet bill to do what amounts to a SQLite read + a `printf`. The triage layer routes those to a Python script that does exactly the SQLite read and the printf, with Haiku composing the natural-language wrapper. The container is bypassed entirely.

**Shadow mode makes the rollout debuggable.** Phase 2a ships the triage layer with the bypass switch OFF — every classification decision logged to `data/haiku-triage-decisions.jsonl`, every message still flowing through to a container. After a week of logs, we'll see exactly which classifications would have short-circuited correctly and which would have produced a wrong answer. The flip from shadow to live is gated on the measured false-positive rate being under 5%. If the data says it's higher than that, we tune the prompt or the threshold before flipping — no production user sees a bad answer.

Conservative projection from the design doc, after measured per-call cost ($0.000577 for the live test): ~$220-360/month. Higher-volume estimate, once Phase 2b is well-tuned: ~$375/month. Combined with Phase 1's deterministic shortcuts (which catches the absolute-cheapest at $0): ~$400-500/month from the routing layer alone.

The wider pattern is *small models as workflow primitives*. Treat the cheap model not as a worse version of the strong model, but as a different kind of component — a router, a triage gate, a formatter, an oracle for "is this even worth spawning the strong model for?" The cost structure makes them effectively free for that role, and the asymmetry between miss cost (a follow-up spawn) and hit value (a full spawn avoided) does the rest.

## What's left, and what we learned

Three meta-lessons worth keeping:

**Observability is the entire game.** Every fix in this list came after a measurement told us where the cost was hiding. We had MTD totals and cache-hit rates from day one, but no per-spawn attribution, no per-channel volume, no per-tier breakout, no spawn-level cost alerts. The first day of the investigation produced almost no fixes — it produced the *audits* that produced the fixes the next day.

**Tier-aware pricing should be tracked from day one.** Anthropic's pricing has multiple axes: model, context tier, cache state. Our tracker collapsed all of them into a single per-model rate. Fixing it took 90 minutes of careful work + 58 tests, but the cost of *not* fixing it was a 26% silent under-reporting on the bill we use to make capacity decisions. If you build a tracker on day one, build it tier-aware.

**Conservative defaults beat optimistic defaults.** The `skill_detected → Opus` shortcut was an optimistic default — "skills imply complex reasoning, so route them to the best model." In practice, most skill invocations are routine. Conservative defaults — Sonnet for skills, with an explicit Opus opt-in for the few that genuinely need it — saved more than the boundary tuning ever would. The same logic applies to the 1M-context tier: it's a flag you opt into for the rare conversation that needs it, not a default.

The system itself reviewed this draft in Notion before publication. The next part covers what happens after cost is under control — the question that's harder than "how much does it cost" is "what do we want it to do."
