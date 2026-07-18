---
title: "Unclogging the Pipeline — When 'Merged' Quietly Stopped Meaning Merged"
slug: 12-unclogging-the-pipeline
series: How BitSafe Runs on Notion
part: 12
published: 2026-07-18
audience: [App Developers, Trading Firms, Founders]
---

# Unclogging the Pipeline — When 'Merged' Quietly Stopped Meaning Merged

This is Part 12 of BitSafe's NanoClaw case study series. Part 7 argued that every line of automation that doesn't tell you when it's broken *is* broken — eventually, silently, in a way that's expensive to discover. This part is that argument's sharpest example to date: the deploy pipeline itself stopped delivering, roughly twenty finished changes piled up behind it, and every dashboard stayed green the whole time.

The pipeline in question is the one that gets a code change from "an agent pushed a branch" to "it's running in production." A branch is pushed; CI runs lint, typecheck, and the test suite; if green, a webhook posts the branch to an **auto-promote listener** that watches a 30-minute smoke window on the dev VM, runs an adversarial code review, and — if all of that passes — merges to `main` and flags a production restart. On a good day a human never touches it. That's the point.

Then, for a stretch in early July, it silently stopped.

## The symptom: green everywhere, shipping nowhere

There was no alarm. That's the whole story in one sentence. The service was up. CI was green on every branch. The listener process was running and answering health checks. And roughly twenty branches — each with passing CI, each representing finished, reviewed work — sat unmerged, some for days.

The reason nobody saw it is that no single monitor owned the gap the failure lived in. We had a stall detector, but it only recognized one failure shape: a promote that merged locally and then failed to push (a "merged-but-not-pushed" marker it could grep for). We had a CI-health snapshot that *warned* when a branch was green-but-unmerged for more than four hours — but warning is not the same as acting, and nothing in the system re-enqueued a branch that had fallen out of the queue. The dashboards were all reporting on the wrong side of the clog. "CI passed" was true. "Landed on `main`" was false. The space between those two facts had no keeper.

> A green checkmark on every branch and an empty release are not a contradiction the dashboards can see — unless something is explicitly watching the *gap* between "passed" and "landed."

## The root cause: an in-memory queue meets a restart on every merge

The auto-promote listener held its promote queue **in memory only**. Branches waiting their turn, and the branch currently promoting, lived in a Python data structure and nowhere else.

Separately — and this is the collision — nearly every successful merge touches a `restart-pending` flag, because most merges ship code that the long-running production process needs to reload. A helper picks up that flag and restarts services. And the restart didn't discriminate: it bounced the auto-promote listener too.

So the failure was structural and quiet. A merge lands → `restart-pending` is set → the restarter bounces the listener → **the in-memory queue evaporates** → every branch that was queued or mid-promote is simply gone. No exception, no log line that reads like an error, no stall marker for the detector to find. The next branch to arrive promotes fine, which makes the pipeline look alive. The dropped ones just... aren't there anymore, and nothing remembers they were supposed to be.

Two secondary failures compounded it. First, the single-flight queue had no *deduplication* by commit identity, so a branch that got posted more than once (a webhook plus a re-fire plus a recovery sweep) would drain each copy into its own full 30-minute promote — one branch burned ninety minutes promoting the same commit three times, each ending in the same review hold. Second, the adversarial reviewer was diffing a **stale local branch reference** instead of the exact pushed commit, so a branch that had already been hardened kept getting re-reviewed against its *old* code and held on issues that no longer existed — trapping finished work behind a review that could never pass.

## The unclog: detection, recovery, and prevention

The fix wasn't one commit; it was a small family of them, and they map cleanly onto three jobs. This is the shape most silent-failure fixes take here, so it's worth naming.

**1. Recovery — turn the warning into an action.** We already *detected* stranded branches (the four-hour CI-health warning). What was missing was a hand to pick them back up. A new sweep reads that same stuck-branch signal, re-verifies each branch is genuinely unmerged, and re-posts it to the listener — bounded by a per-branch cooldown, a per-branch attempt ceiling that escalates to a human instead of retrying forever, and a per-run cap so a bad state can't flood the queue. A detect-only alarm had been leaving the work stranded until a person noticed; now detection is wired to recovery.

**2. Prevention — stop dropping the queue in the first place.** The recovery sweep is a safety net, not a cure. The cure was to stop bouncing the listener on merges that have nothing to do with it. The restart helper now **content-hashes the listener's own source file** and only restarts it when that hash actually changes. The listener imports only the standard library and shells out to a fresh promote script per job, so its code is the *only* thing whose change requires a restart — which means the roughly ninety-five percent of merges that don't touch it now leave its queue untouched. The gate fails safe: on any state it can't classify, it restarts anyway, so we never trade this fix for a stale-code bug.

**3. Hygiene — dedup the queue and review the right code.** Duplicate posts of the same commit are now dropped at the door with an "already queued" acknowledgement, keyed on `(repo, ref, sha)`, so one commit can't spawn three promotes. And the adversarial reviewer now diffs the **resolved commit SHA it's actually about to merge**, not a branch name that might point at stale local state — so hardened branches stop getting held against code they no longer contain.

```text
Before:  push → CI green → queue (in memory) → restart drops it → gone, silently
After:   push → CI green → queue (dedup'd) → restart gated on listener-code-change
         → if it still strands, recovery sweep re-posts it (bounded) → merged
```

## What it cost, and what it taught

The direct cost was throughput: for the duration, humans were manually merging what the pipeline should have merged itself, which both masked the failure (the work *was* landing, just by hand) and burned the reviewer's attention on mechanics. The manual path is the tell. When you find yourself doing something by hand that a machine is supposed to do, the machine is broken — and if the manual workaround is cheap enough, nobody feels the cost directly, so the broken automation can stay broken indefinitely. We now treat "I merged that one myself" as an incident signal, not a convenience.

Two lessons generalize past this pipeline:

> **A detect-only alarm without an automatic recovery leaves the work stranded until a human acts.** Warning that something is stuck is worth little if nothing unsticks it. Pair every "this is stuck" signal with either an auto-recovery or an explicit escalation that names a person.

> **An in-memory queue with no persistence strands its contents on every restart.** If a queue holds work that matters, either persist it or make absolutely sure nothing restarts the thing that holds it. We chose the latter as the immediate fix and left durable queue persistence as the deeper follow-up — a band-aid honestly labeled as one, with the structural fix named and tracked rather than assumed done.

The pipeline moves again. More importantly, the *gap* between "CI passed" and "landed on `main`" now has a keeper: a sweep that watches it, a restart that respects it, and a rule that a human merging by hand is a symptom to investigate, not a habit to normalize.

---

*Related: [Part 7 — Monitors & Alerts](07-monitors-and-alerts.md) (why an unwatched check is no check), [Part 10 — The Completeness Trap](10-completeness-trap.md), and [Part 11 — Retros, Recursively](11-retros-recursively.md) (how incidents like this become durable rules).*
