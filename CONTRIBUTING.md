# Contributing to bitsafe-ai-docs

Thanks for your interest. Here's how to submit changes.

## Issues

- Typos, broken links, factual errors: open an issue with the section + the fix.
- Discussion / feedback on framing: open an issue tagged `discussion`.

## How changes land

**Article content auto-merges to `main` — there is no human approval step.** The
README-freshness guard (pre-commit hook + CI) is the only gate. The default flow is
**push article commits straight to `main`**:

1. Make the change — prose, code snippet, or new article.
2. If you added a new article, update **both** README indexes in the same commit (the
   freshness guard below blocks any commit/push that forgets this).
3. Commit and push to `main`. That's it — content is live; no PR review, no approval.

The pre-commit hook runs the freshness guard locally; the `check-readme-articles` CI
workflow re-runs it on every push to `main`. Either one failing is the *only* thing
that blocks an article from landing.

### Outside contributors / optional PR flow

Don't have push access? Open a PR:

1. Fork + branch from `main`, make the change, update the README indexes, open a PR.
2. The freshness CI check must be green. There is no required human reviewer — once the
   check passes the PR can auto-merge (`gh pr merge --auto --merge`).
3. Expect the adversarial reviewer bot to argue against your change. That's the system
   working as intended; respond to the substance. It does not block the merge.

## Article style

Follow the BitSafe Content Strategy + Brand Guide (internal — abridged here):
- Specific examples beat abstractions.
- "We did X because Y" beats "you should X."
- Numbers + dates + commit SHAs make claims credible.
- ≤2 pull-quote lines per article, max.
- No marketing fluff.

## Adding a new article (and the README freshness guard)

Every `docs/articles/NN-*.md` source file MUST be listed in **both** indexes:

- the series table in the top-level [`README.md`](README.md)
- the source-file table in [`docs/articles/README.md`](docs/articles/README.md)

This is the **only gate on the auto-merge flow.** Adding an article file without updating
the indexes is a hard failure; everything else lands automatically:

- **Locally (the gate that matters for direct-to-main):** run `bash scripts/install-git-hooks.sh`
  once after cloning to install a pre-commit hook that runs the freshness check before every
  commit. A commit that adds an unindexed article is rejected before it can be pushed. Bypass
  (rarely) with `git commit --no-verify`.
- **CI:** `.github/workflows/check-readme-articles.yml` re-runs the same check on every push to
  `main` (and on PRs) so a `--no-verify` bypass or a fork PR is still caught.

The guard blocks *unindexed articles*. It does **not** require human approval — content with a
fresh README index merges to `main` with no review step.

Run the check manually any time: `bash scripts/check-readme-articles.sh`.
Test the guard itself: `bash scripts/test-check-readme-articles.sh`.

## Code snippets

- Apache 2.0 licensed (matches the framework upstream).
- Working examples, not pseudo-code.
- Test before committing.

## Security

If you find a vulnerability, do NOT open a public issue. See `SECURITY.md`.
