# Contributing to bitsafe-ai-docs

Thanks for your interest. Here's how to submit changes.

## Issues

- Typos, broken links, factual errors: open an issue with the section + the fix.
- Discussion / feedback on framing: open an issue tagged `discussion`.

## Pull requests

1. Fork + branch from `main`.
2. Make the change — prose, code snippet, or new article.
3. Open a PR. Describe what changes + why.
4. Expect the adversarial reviewer to argue against your change. That's the system working as intended; respond to the substance.
5. Merge happens after one BitSafe maintainer approves.

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

This is enforced. Adding an article file without updating the indexes is a hard failure:

- **CI:** `.github/workflows/check-readme-articles.yml` runs on every push/PR that touches
  `docs/articles/**` or `README.md` and blocks merge if an article is unindexed.
- **Locally:** run `bash scripts/install-git-hooks.sh` once after cloning to install a
  pre-commit hook that runs the same check. Bypass (rarely) with `git commit --no-verify`.

Run the check manually any time: `bash scripts/check-readme-articles.sh`.
Test the guard itself: `bash scripts/test-check-readme-articles.sh`.

## Code snippets

- Apache 2.0 licensed (matches the framework upstream).
- Working examples, not pseudo-code.
- Test before committing.

## Security

If you find a vulnerability, do NOT open a public issue. See `SECURITY.md`.
