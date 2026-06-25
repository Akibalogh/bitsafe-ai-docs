---
title: "Docs as Code — When Your Catalog of Capabilities Goes Stale, the AI Goes Blind"
slug: 12-docs-as-code
series: How BitSafe Runs on Notion
part: 12
published: 2026-06-25
audience: [App Developers, Trading Firms, Investors]
---

# Docs as Code — When Your Catalog of Capabilities Goes Stale, the AI Goes Blind

This is Part 12 of BitSafe's NanoClaw case study series. Earlier parts argued for moving rules out of memos and into mechanisms, and for making coverage decisions explicit instead of accidental. This part applies the same instinct to the most boring artifact in the system — the documentation that tells the AI what it can do — and shows why getting its source of truth backwards quietly degrades every agent in the fleet.

The framing point: a coding agent only uses the capabilities it knows it has. Its knowledge of what's available comes from docs — the per-skill `SKILL.md` files that describe a tool, the commands to invoke it, and when to reach for it. If those docs drift from the code, the agent doesn't error. It just stops reaching for things that exist. Stale capability docs don't produce a crash you can trace; they produce *capability-blindness*, an agent that hand-rolls something a skill already does, or skips a real tool because the doc describing it is wrong. That's the most expensive kind of bug, because nothing fires.

## The inversion we had backwards

NanoClaw's skills are the agent's tool catalog — one folder per skill, each with a `SKILL.md` that documents the commands and the intent. For a long stretch, the *source of truth* for those docs was Notion. The Notion "Skills" database was canonical; the on-disk `SKILL.md` copies were a cache, re-synced from Notion to disk on a schedule. Editing meant editing the Notion row, and an hourly job clobbered the on-disk copy to match.

This is exactly backwards, and the symptoms compounded quietly:

- **Drift had no brake.** A `SKILL.md` describing the command for a tool could fall behind the actual code, and nothing checked. The doc and the code it described lived in different systems with no contract between them.
- **The catalog outgrew reality.** A measured snapshot found **363 Notion skill rows against 140 actual git-tracked skills** — more than twice as many catalog entries as real capabilities. Dead rows, renamed-and-orphaned rows, speculative rows that never shipped.
- **A third of the catalog was undescribed.** **34% of skills had no description** in the canonical store — present as a name, blank where the agent needed to learn what they do and how.
- **Edits didn't stick.** An on-disk fix to a `SKILL.md` was the natural place to make a change while working in the code — and it was wiped on the next hourly sync, because disk was downstream of Notion. The right place to edit was the place least connected to the code.

None of this threw an error. It showed up as agents that were subtly less capable than the system actually was — reaching for the wrong tool, or no tool, guided by a catalog that had quietly diverged from the codebase.

> Stale capability docs don't crash. They make the agent blind to capabilities it actually has — and the most expensive bug is the tool the model never reaches for because the doc describing it is wrong.

## Flipping the source of truth

The fix is to treat docs the way you treat code, because in an agent system the docs *are* part of the runtime — they're the model's map of its own abilities. So we inverted the flow:

1. **Docs are git-canonical.** The `SKILL.md` files live with the code, in version control. They're PR-reviewed like code, and an edit takes effect immediately — no sync round-trip, no clobber. The place you naturally edit while working in the code is now the authoritative place.
2. **A doc↔code contract test makes drift a CI failure.** A test reads each `SKILL.md`, extracts the commands it documents, and asserts they match what the code actually exposes. When a doc's documented invocation drifts from the code, the build goes red and names the offending skill. Drift stops being an invisible slow leak and becomes a deterministic, blocking event at the moment it's introduced.
3. **Catalogs are generated, so they can't drift.** The human-readable cheatsheet and the Notion catalog are now *outputs*, regenerated from the git-canonical docs. A generated artifact can't fall out of sync with its source by definition — if the source changes, the next generation reflects it; if it doesn't regenerate, that's a pipeline failure you can alarm on, not a silent divergence.
4. **Sync is one-way: git → external, never external → clobber.** Notion becomes a read-only, generated mirror, written one direction (on-merge and daily). Nothing external can overwrite the canonical copy. The hourly clobber that ate on-disk edits is gone, because the arrow only points outward.

## The reusable principles

Strip away the specifics and four principles generalize to any system where an AI's behavior depends on docs:

1. **Docs-as-code.** Documentation that the runtime depends on — capability catalogs, tool specs, command references — lives *with* the code it describes, version-controlled and reviewed. Distance between a doc and its code is the room drift grows in; eliminate the distance.
2. **A doc↔code contract test.** If a doc claims the code does X, a test should fail when the code stops doing X. Make doc drift a deterministic, named CI failure instead of a thing someone notices weeks later. This is the same mechanism-over-memo move applied to docs: the test is policed by the build, not by a human remembering to check.
3. **Generated catalogs can't drift.** Anything that's a *view* of the source — a cheatsheet, an external mirror, an index — should be generated from the source, not hand-maintained alongside it. A generated artifact is structurally incapable of disagreeing with its source.
4. **One-way sync, never reverse-clobber.** When you mirror canonical data to an external system for visibility, the arrow points one direction only. The moment the external copy can write back over the source, the external copy becomes a second, unreviewed source of truth — and the less-connected one usually wins by being the easier place to edit.

## The meta-lesson

The instinct that keeps recurring in this series is *put the fact in one place, and make a machine enforce that everything else defers to it.* Part 8 applied it to capability awareness via harness guards; Part 9 applied it to guard coverage via a registry. Part 12 applies it to the documentation itself: the docs an agent reads to know what it can do are not commentary about the system — they are part of the system's behavior, and they deserve the same source-of-truth discipline as code.

The general principle, for anyone building agent systems: your AI is exactly as capable as its catalog says it is, not as capable as your codebase actually is. If those two drift, the AI shrinks to the catalog — silently. So treat the catalog like code, test it against the code, generate every view of it from one source, and let the sync run one direction only. The version that fails loudly when the doc lies is worth far more than the version that's prettier to read and quietly wrong.
