# BitSafe AI Docs

> **BitSafe's company-wide AI: built to run the company and advise the company.**
>
> A case study + the docs to learn from BitSafe's implementation of [NanoClaw](https://github.com/qwibitai/nanoclaw).

## What this repo is

The docs (with worked examples) for how BitSafe — a crypto-finance startup building on the Canton Network — uses NanoClaw to run day-to-day operations and to advise on strategy.

This is **case study content**, not a framework manual. The upstream NanoClaw project at `qwibitai/nanoclaw` is the framework; this repo is BitSafe's implementation, customizations, and lessons.

## The article series

| # | Layer | Title | Source | Status |
|---|---|---|---|---|
| 1 | Infra + Security | [Building a Company-Wide AI Assistant](https://hub.bitsafe.finance/company-wide-ai-assistant) | [`01-company-wide-ai-assistant.md`](docs/articles/01-company-wide-ai-assistant.md) | published |
| 2 | Foundation | [NanoClaw Architecture](https://hub.bitsafe.finance/nanoclaw-architecture) | [`02-architecture.md`](docs/articles/02-architecture.md) | published |
| 3 | Operations | The Autonomous Engine — Loops, CI/CD, ARQ + Swarms, Observability | [`03-autonomous-engine.md`](docs/articles/03-autonomous-engine.md) | drafting |
| 4 | Substrate | The Substrate — Notion-as-OS, Data, Code, Knowledge, and Tools | [`04-substrate.md`](docs/articles/04-substrate.md) | drafting |
| 5 | App / Top | Working With NanoClaw — Personas, Alerts, Memory, Decision Support, and How Humans Teach the AI | [`05-working-with-nanoclaw.md`](docs/articles/05-working-with-nanoclaw.md) | drafting |
| 6 | Lessons | [Cost Discipline — Why the Bill Grew, What We Caught, How to Catch It Sooner](https://hub.bitsafe.finance/cost-discipline) | [`06-cost-discipline.md`](docs/articles/06-cost-discipline.md) | published |
| 7 | Lessons | Monitors & Alerts — Catching What You Can't Prevent | [`07-monitors-and-alerts.md`](docs/articles/07-monitors-and-alerts.md) | drafting |
| 8 | Lessons | Capability Coverage & Harness Guards — Why the Model Shouldn't Have to Remember What It Can Do | [`08-capability-coverage-and-harness-guards.md`](docs/articles/08-capability-coverage-and-harness-guards.md) | drafting |
| 9 | Lessons | Guard Parity — A Guard Only Protects Where It's Wired | [`09-guard-parity.md`](docs/articles/09-guard-parity.md) | drafting |
| 10 | Lessons | The Completeness Trap — You Can't Audit Your Own Blind Spots | [`10-completeness-trap.md`](docs/articles/10-completeness-trap.md) | drafting |
| 11 | Lessons | Retros, Recursively — How the AI Studies Its Own Output | [`11-retros-recursively.md`](docs/articles/11-retros-recursively.md) | drafting |

Articles are published as-ready to BitSafe's hub (`hub.bitsafe.finance`); drafts and source live here.

## Specs

Forward-looking architecture proposals (separate from the retrospective case-study articles).

| Spec | Source |
|---|---|
| Code Factory MVP — 24x7 Autonomous SDLC Pipeline | [`code-factory-mvp-spec.md`](docs/specs/code-factory-mvp-spec.md) |

## Contributing

Issues + PRs welcome. The system itself reviews proposed changes — there's an adversarial reviewer bot that argues against any PR by default (it's a feature). Address it head-on in your PR description and you'll have an easier review.

See `CONTRIBUTING.md` for specifics.

## License

- Prose (articles, docs): [CC-BY-SA-4.0](LICENSE-DOCS)
- Code snippets and any tooling: [Apache 2.0](LICENSE)

## Links

- Upstream framework: [qwibitai/nanoclaw](https://github.com/qwibitai/nanoclaw)
- BitSafe public hub: [hub.bitsafe.finance](https://hub.bitsafe.finance)
- BitSafe: [bitsafe.finance](https://bitsafe.finance)
