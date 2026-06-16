---
title: "Guard Parity — A Guard Only Protects Where It's Wired"
slug: 09-guard-parity
series: How BitSafe Runs on Notion
part: 9
published: 2026-06-16
audience: [App Developers, Trading Firms, Investors]
---

# Guard Parity — A Guard Only Protects Where It's Wired

This is Part 9 of BitSafe's NanoClaw case study series. Part 8 made the case for *harness guards over memos*: when a rule keeps getting broken, you stop writing it down and start enforcing it in the mechanism, because a memo is policed by the same fallible process that produces the violation, and a guard is not. This part is about the failure mode that lives one level up from that lesson. You did the right thing — you moved the rule into a guard. The guard works. And the violation happens anyway, because the guard was wired into one actor's path and the actor that broke the rule runs somewhere else.

The framing point: in a system with more than one kind of actor, "we have a guard for that" is only true per-actor. A guard is not a property of the system. It is a property of the code path it sits in. If you have two code paths and the guard is in one, you have half a guard — and the half you're missing is invisible, because the guard genuinely fires everywhere you look for it.

## Two surfaces, two runtimes

NanoClaw runs two classes of actor. The **host loop** is the operator-facing session — the one a human drives, the one that dispatches work. The **container agents** are the sandboxed workers: one per task, running the model with a tool surface, doing the actual reading and writing and posting. Most of the work — almost all of it — happens in the containers. The host mostly decides and delegates.

Each surface has its own guard mechanism, and they are not the same technology. Host guards are declarative hooks wired in a settings file, implemented as small scripts. Container guards are callbacks compiled into the agent image, implemented in the image's own language. Different runtime, different config format, no shared code path. You cannot copy a guard from one to the other; you re-implement it. And the moment a guard requires re-implementation to cross the boundary, the default outcome is that it *doesn't* cross — someone adds it where they're working and moves on.

> A guard is not a property of the system. It's a property of the code path it sits in. Two paths, one guard, means half a guard — and the missing half is invisible.

So drift is not an occasional accident. Drift is the *default*. Every new guard starts life on exactly one surface. Staying single-surface is the path of least resistance, and nothing pushes back.

## The incident that named it

We had built a guard whose whole job was to stop a specific bad reasoning habit: asserting a *cause* for a failure before running the cheap check that would confirm it. ("This credential is broken" — without probing the credential. "This is IAM-blocked" — without checking the token's scopes.) The guard fires on access/auth-failure tool results and injects a "verify first" interrupt before the model can rationalize. It worked well. It was wired into the host loop.

Then a container agent hit a failing push, declared the credential broken, and asked for a new one — the exact move the guard exists to stop. The credential was fine. The operator's reaction was reasonable: *the guard isn't working.* But it was working. It just wasn't running where the work happened. The guard lived in the host session's config; the agent that broke the rule was a container, which never reads that config. We had built the guard, verified the guard, and watched the guard do nothing — because "we have a guard for that" had quietly meant "the host has a guard for that" the whole time.

It recurred in a different shape within the same stretch. A fix to one content-writing helper — make sure the page body actually gets written, not just a truncated property — was correct and shipped. Its sibling helper, doing the same job through a different tool, had the same bug and didn't get the fix. A container agent used the sibling, reported "filed, with the full spec," and produced an empty page. Same root: a fix that protects one path is not a fix for the class. The mechanism-level lesson from Part 8 is necessary but not sufficient — you also have to make the mechanism *cover every actor*, and prove that it does.

## Not blind parity

The naive correction is "put every guard on every surface." That's wrong, and the registry below is explicitly built to *not* do it. Some guards are correctly single-surface. The host has a guard that repairs environment-file permissions; containers are read-only and have no such file, so porting it would be meaningless. Containers have an egress firewall and a bash-sanitizer; the host's shell is operator-trusted, so those don't belong there. The point is not symmetry. The point is that every guard's surface coverage should be a *decision someone made on purpose and wrote down* — not an accident of where the author happened to be working.

That reframes the problem from "achieve parity" to "make the coverage decision explicit and enforce that it was made." Which is a thing software can check.

## The registry and the drift-detector

The fix is a single catalog — one manifest that lists every guard with the surfaces it's supposed to run on, the implementation on each surface, and, for any guard that runs on only one surface, the reason. It's the same shape as the canonical roster pattern from earlier in the series: the fact lives in exactly one place, and everything else refers to it instead of re-deriving it.

The teeth are a continuous-integration check that reads the manifest and refuses the build unless three things hold. Every guard's *declared* surfaces have a *real* implementation present on each of them. Every guard *actually wired* on a surface is *present in the manifest* — so you cannot add a guard to either surface without registering it, which is the moment you're forced to answer "does this need the other surface too?" And every single-surface guard carries a written rationale. Add a guard to the container and forget the host, or forget to record why it's container-only, and the build goes red with the offending guard named.

This converts the invisible default (drift) into a loud, blocking, named event at the exact moment it's introduced. It is the same move as Part 7's silent-failure layer, applied to guards instead of crons: the absence of a decision becomes a signal. A refinement extends it to the rules themselves — the shared pattern lists a guard matches against (failure markers, sensitive-term lists) are pulled into one data file both runtimes load, so even the *contents* of a guard can't drift between surfaces while the code stays per-runtime.

## The meta-lesson

Part 8 said: when a rule keeps breaking, move it from a memo into the mechanism. Part 9 is the necessary follow-on: a mechanism only governs the actors whose path it's in, so the mechanism that *keeps the mechanisms honest* has to be one a human can't forget to run. A memo that says "remember to add new guards to both surfaces" is exactly the kind of memo Part 8 told you not to trust — it's policed by the same person who's about to forget. The registry can't be forgotten, because the build won't go green until the coverage decision exists. The guard on the guards is itself a guard, not a note.

The general principle, for anyone building multi-actor agent systems: count your actors, and for every safety property you care about, ask not "do we have a guard for this" but "is this guard wired into every path that can violate it, and what enforces that it stays that way." The first question has a comforting answer that is usually a little bit false. The second one is the one that's actually load-bearing.
