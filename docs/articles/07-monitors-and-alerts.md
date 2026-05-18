---
title: "Monitors & Alerts — Catching What You Can't Prevent"
slug: 07-monitors-and-alerts
series: How BitSafe Runs on Notion
part: 7
published: 2026-05-18
audience: [App Developers, Trading Firms, Investors]
---

# Monitors & Alerts — Catching What You Can't Prevent

This is Part 7 of BitSafe's NanoClaw case study series. Parts 1-5 covered architecture, autonomy, and the daily working pattern. Part 6 was a cost-discipline postmortem: the observability gap that let the bill grow past plan and the layers we built so it can't again. Part 7 generalizes that lesson. Every line of automation that doesn't tell you when it's broken *is* broken — eventually, silently, in a way that's expensive to discover. This part walks through the four signal channels NanoClaw uses to surface what crons and monitors find, the real incidents that taught us the gaps, and the prevention layers we've now wired in.

The framing point first. A "monitor" in a humanly-operated system is a graph someone looks at. In an autonomously-operated system, where most of the actors are not humans, a monitor has to be a *message that arrives in front of a person who can act on it*. If the graph exists and no one's watching it, it might as well not exist. The work of the last few months has been less about adding checks (we already had dozens) and more about making sure the checks **surface** to a place where the right person sees them, in a form that's distinguishable from noise.

## The four signal channels

Every cron, monitor, or recurring analysis in NanoClaw produces an output. We classify each by where that output goes, because the failure mode is different at each layer:

**Channel 1 — Alarms.** Time-sensitive, actionable findings that need a human (or another agent) to react now. Implementation: `scripts/ping-aki.sh --to admin --source <name> --severity warning|critical`, which posts to `#ai-projects-nanoclaw-admin` with an `@` mention. Cooldown-gated (typically 6h) so a stuck condition doesn't carpet-bomb the channel. Examples: `warm-pool-alarm` when no warm container is available for incoming work, `stale-tasks-alarm` when a scheduled task hasn't fired in its expected window, `env-perms-alarm` when `.env` ownership drifts and the service can't read its own secrets, `restart-churn-alarm` when the systemd unit has bounced more than 20 times in a day. The audience is the on-call human, which is almost always Aki (and now sometimes Kadeem). When this channel fires, *someone is supposed to drop what they're doing*.

**Channel 2 — Reports.** Analyses that produce a structured document for periodic review. Implementation: the script writes a Notion page in the NanoClaw pillar of the workspace, with a dated title (`Blocked Tasks Triage — 2026-05-18`, `Admin Text Backfill — 6 weeks — 2026-05-18`, `Origin Branch Cleanup — 2026-05-18`). The page contains classification counts, sample rows, and one-click links to the underlying items. Cron-driven (weekly or monthly), so the rhythm matches the audience's attention. When this channel fires, *the human looks during a planned review window*, not immediately.

**Channel 3 — Status digest.** The catch-all daily dashboard. A scheduled task named `monitor-daily-dashboard` fires at 09:00 UTC, calls `buildDashboardPrompt()` in `src/monitor.ts`, and renders sixty-plus health checks (cost vigilance, sync staleness, CI/CD pipeline status, container error rate, scheduled-task drift, audit-log anomalies) into one Slack message in the admin channel. This is the "running gauge" view: nothing's screaming, but here's where every monitored signal currently sits. When this channel fires, *the human scans for red and yellow chips*, looking for the latent drift the alarm thresholds were tuned not to catch.

**Channel 4 — Forensic logs.** Everything else. `/root/nanoclaw/logs/<x>.log`. These are write-only most of the time; nobody reads them unless investigating a specific symptom. They exist for the case "something feels wrong, let me check what the last 24h of cron output looks like." Useful when needed; mostly invisible otherwise.

The pattern is hierarchy: most actionable to least actionable, most time-sensitive to least. Every recurring analysis picks exactly one channel as its primary surfacing path, and ideally a second as backup.

## The gap class: silent failures *of the monitors themselves*

Here's where it gets recursive. A monitor that has been silently broken for a week is worse than no monitor at all — it gives you the false confidence of "I'd know if something were wrong." Through May 2026 we found multiple instances of this exact shape:

- `worktree-auto-reaper` was running on a daily cron, but its commit had flipped only the *doc mirror* of the cron line, not the live `/etc/cron.d/nanoclaw`. The live cron continued running in `--dry-run` mode for two weeks. The reaper produced clean log output saying it "would" delete merged worktrees. Sixty-six orphan worktrees accumulated.

- The Anthropic MTD tracker's `last_updated` field hadn't moved in 18 hours when we last checked. The daily sync cron had silently failed (likely a Google Drive auth refresh issue). The dashboard correctly showed the MTD number — but the number was 18h stale, and the over-reporting from a separate tier-pricing bug compounded the staleness invisibly.

- Five EACCES test failures in `container-mounts-cheatsheet.test.ts` had been failing every dev-deploy CI run for more than 24 hours. The CI fired correctly. The tests ran correctly. The result was correctly reported as "failure." But no monitor watched the *aggregate dev-deploy success rate*, so nobody noticed the pipeline had stopped advancing.

The class is: each individual layer is technically working. The integration — *did anyone notice that the layer was working but the work wasn't getting done?* — was the gap.

## The silent-failure layer

This is where we landed after the May postmortems. Two new monitors, both rendering into the daily dashboard, both backed by a script + cron entry, both intended to surface the *meta-question*: "are the things that are supposed to run, actually running?"

**Cron-success check.** Reads `/etc/cron.d/nanoclaw`, parses each line for its expected interval and its `>> <log>` redirect target, and confirms each log file's mtime is fresher than `interval × 1.5`. If `warm-pool-alarm.sh` is supposed to run every 5 minutes and its log hasn't been touched in 401 minutes, that's flagged. If `arq-sleep-detector` is supposed to run every 90 minutes and its log is 18,518 minutes (~13 days) old, that's flagged. On a single ship-time run, this check found **eleven stale cron log redirects** — every one a script that was supposed to be running and wasn't. Eleven. The framing point above is not theoretical.

**State-file freshness check.** Reads a config at `data/state-file-cadences.json` mapping each `data/*-state.json` file to its expected refresh cadence, then checks each file's mtime against that cadence. State files are where most NanoClaw scripts persist their "last successful run" timestamp; a stale state file means the script either failed to complete or didn't run at all. The same ship-time run found **seventeen stale state files**, with the worst at 651 hours (twenty-seven days) old.

Both checks render into the daily dashboard with red/yellow/green chips per flagged item. Both are about to get a second surfacing path: a threshold-based admin ping at the moment new flags appear (cooldown-gated, same pattern as `warm-pool-alarm`), so a fresh silent failure doesn't have to wait up to 24h for the daily digest to surface it.

## The handled-check layer

Even with surfacing fixed, there's a downstream question: when an alarm lands in the admin channel, did anyone *act* on it? Or did it scroll off the top of the channel while everyone was busy?

The pattern we're adding is a weekly "handled-check" sweep. A script reads the last 7-14 days of `#ai-projects-nanoclaw-admin` messages, filters to alarms/reports posted by bots (admin-bot, the various `nanoclaw-*` alarm sources), and classifies each as HANDLED or UNHANDLED. The classifier is heuristic but concrete:

- A human reply in the thread within 24 hours → HANDLED
- A Tasks DB row references the alarm (search by alarm source / id) → HANDLED
- A commit or branch on origin mentions the alarm topic within 48 hours → HANDLED
- The underlying condition has cleared (e.g., the stale cron is now running again) → HANDLED
- None of the above → UNHANDLED

UNHANDLED items get a weekly Notion report listing the permalinks. If the count crosses a threshold (default: 3), it pings admin with a one-line digest. This is the closing-the-loop layer: alarms get into the channel, the channel gets monitored, and unhandled alarms get surfaced as *their own* second-order signal.

## The action-items extraction layer

There's an inverse problem that lives in the same neighborhood. When admin-bot produces a substantive technical reply — a research finding, a recommendation table, a postmortem with action items — those items frequently lived in the Slack thread and never made it into the Tasks DB. The recommendations were structurally there ("Layer | What to do | Why" tables) but no parser was extracting them.

The fix is two-sided. First, admin-bot's response template now requires an `## Action items filed` section at the end of every substantive reply, enumerating the Tasks DB rows it created (with permalinks) — or stating "Informational only, no action items" explicitly. Second, a belt-and-braces post-hook scans admin-bot's outbound messages for recommendation patterns (tables, "should X" verbs, imperative lists) and creates Tasks DB rows for anything the response-template change missed.

Together with the handled-check above, the loop closes on both sides:
- Tasks get *filed* when they're created (user → admin-bot direction caught by audit-mentions; admin-bot → recommendations caught by the response template + extractor).
- Tasks get *followed up on* when they sit unhandled (handled-check sweep).

Neither layer is glamorous. Both layers are the work of making sure the system doesn't quietly drop things.

## The threshold-ping pattern, generalized

A meta-rule from all of the above: any recurring analysis whose primary output is a Notion page or a dashboard chip needs a *second* surfacing path keyed off a threshold. The Notion page is where the human goes to *read*; the threshold ping is what *causes* the human to go read.

The pattern is:

1. Compute the finding count (new flags, new unhandled items, new pending substitutions, new whatever)
2. Compare against the last-success state file: how many of these are NEW since the last alarm fire?
3. If `new_count > threshold` AND `last_alarm_fire > cooldown` → fire ping-aki with a one-line digest
4. Update the state file

Across NanoClaw today this pattern is wired into: warm-pool-alarm, stale-tasks-alarm, env-perms-alarm, restart-churn-alarm, the cross-post leak monitor, the bulk-send guard monitor. It's about to be wired into the silent-failure monitors and the deterministic-flows monthly audit. The shape is repeatable enough that it should probably be a shared helper function rather than re-implemented per script.

## What's left

This part of the case study describes a system that's still becoming what it's meant to be. The pieces we have shipped today:

- The four-channel signal taxonomy (alarms, reports, status digest, forensic logs) is in production and documented
- The CI/CD pipeline monitor (ten sub-checks) catches what every other layer didn't catch about deploy pipeline health
- The silent-failure monitors (cron-success, state-file-freshness) catch what every other layer didn't catch about *the rest of the layers*
- The handled-check sweep is filed and spec'd; ships this week

The pieces we're carrying forward:

- Threshold-ping on the silent-failure monitors (closes the up-to-24h surfacing gap)
- A shared `surfacing.fire_threshold_ping(name, count, threshold, cooldown_h)` helper so we stop re-implementing the same five-line pattern
- The action-items extraction layer (response template change + post-hook scanner)
- The admin-channel handled-check loop

The bigger lesson — the one Part 6 named and Part 7 generalizes — is the same: the system gets better not by adding checks, but by making sure the checks are *surfacing in a way the right human can't miss*. Visibility isn't a feature you build once. It's a property you have to keep proving the system still has.

---

**Related reading inside this case study:**
- [Part 2: Architecture](02-architecture.md) — how the host + container split shapes which layers can monitor which surfaces
- [Part 4: Substrate](04-substrate.md) — why Notion + SQLite is the right backbone for the daily digest + report-page pattern
- [Part 5: Working with NanoClaw](05-working-with-nanoclaw.md) — the human side: what changes when alarms become reliable
- [Part 6: Cost Discipline](06-cost-discipline.md) — the cost-vigilance dashboard that became the template for the rest of the surfacing layers
