# What's New

High-level digest of the changes worth knowing about in BitSafe's NanoClaw
implementation. One entry per review period, newest first. Each item links to the
article in the series where the full treatment lives (or will live).

This is deliberately **shallow** — it exists so a reader returning after a few
weeks can see what moved without re-reading the series. Depth belongs in the
articles.

> Maintained by a scheduled review (`scripts/docs-freshness-review.py`). The
> review reports problems and questions; it does not post routine "nothing
> changed" updates.

---

## 2026-07-18 → 2026-08-04

**Two thirds of autonomous task runs were failing while reporting success.**
The agent SDK has its own protection against context-thrash, and when *it* ended
a run it used the `success` subtype. Everything downstream believed the run
worked: no failure streak, no alarm, and — because the exit code stayed zero —
the diagnostics needed to debug it were never written. The label is now assigned
*during* the run, on the original text, because the advice-scrubbing step
destroys the evidence a post-hoc detector would need. Underlying cause of the
thrash itself is still open. → [Monitors & Alerts](articles/07-monitors-and-alerts.md)

**A paused run now tells you what it did.** When a run hit its time or turn
limit before the agent had written any prose, the user got a pause notice with no
content in it — work done, nothing to show. The notice now carries a digest built
mechanically from the run's own tool calls (files read, commands run, sub-agents
spawned), secret-redacted. Deliberately *not* an extra "summarise yourself" turn:
at the moment a brake fires the run is out of budget, so asking the least capable
actor at the worst moment is what made the previous approach unreliable.
→ [Working With NanoClaw](articles/05-working-with-nanoclaw.md)

**The deploy queue stopped losing work on restart.** The promote queue was held
in memory on the assumption that CI would re-fire the merge step. It does not —
a push that already happened never re-fires — so a restart silently stranded
every queued branch. The queue is now on disk. Separately, a deploy timeout was
killing the process *tree* mid-way through an image swap, which left the
container image pin stale and refused every agent spawn until a human
intervened. → [Unclogging the Pipeline](articles/12-unclogging-the-pipeline.md)

**A guard that only protects the operator protects nobody.** One safety guard
existed on the host but had no counterpart inside the containers — that is,
present for the human at the console and absent for the agents actually doing the
work. Guard coverage is now declared in a registry with a parity check, so a
one-sided guard fails CI instead of going unnoticed.
→ [Guard Parity](articles/09-guard-parity.md)

**Three tests were found asserting prose rather than code.** A code-shape lock
matched the symbol it was checking for inside an explanatory *comment*, so
deleting the real call left the test green. A roster consistency check counted a
commented-out entry as present. A third test could be turned red simply by adding
documentation near the code it inspected. All three were found by mutating the
code and watching whether the test noticed — not by reading it. The lesson
generalises past these three: a test that greps source text is only as good as
its ability to tell code from commentary.
→ [The Completeness Trap](articles/10-completeness-trap.md)

**A green branch does not merge itself.** When the automated adversarial review
holds a change, that hold is terminal until a human looks at it — no scheduled
job will ever land it. Worth stating plainly because "it passed CI, the pipeline
will get to it" is a reasonable assumption and a wrong one.
→ [The Autonomous Engine](articles/03-autonomous-engine.md)

**Model tier and SDK currency.** The top routing tier moved to Claude Opus 5, and
the container agent SDK moved up a minor series. Tier changes are coupled to a
context-window setting; changing one without the other degrades quietly rather
than failing, so they are now treated as a single change.
→ [NanoClaw Architecture](articles/02-architecture.md)
