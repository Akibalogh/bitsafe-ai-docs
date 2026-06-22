#!/usr/bin/env bash
# check-readme-articles.sh — fail if any docs/articles/NN-*.md is not indexed in the READMEs.
#
# Why: Aki — "make sure the README is updated when we push new content." A new article
# file that isn't listed in the index is invisible to readers; this is the freshness guard
# that makes "added a file but forgot the index" a hard failure instead of a silent gap.
#
# Checks every article source file is referenced in BOTH:
#   - README.md                 (the public series table)
#   - docs/articles/README.md   (the source-file index)
#
# Usage: scripts/check-readme-articles.sh   (run from repo root or anywhere inside the repo)
# Exit:  0 = all articles indexed; 1 = one or more missing from an index.
set -euo pipefail

# Resolve repo root so the hook works from any CWD.
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

TOP_README="README.md"
ARTICLES_README="docs/articles/README.md"
ARTICLES_DIR="docs/articles"

missing=0

shopt -s nullglob
for path in "$ARTICLES_DIR"/[0-9][0-9]-*.md; do
  fname="$(basename "$path")"
  # README.md is not an article; skip defensively (pattern already excludes it).
  [ "$fname" = "README.md" ] && continue

  if ! grep -qF "$fname" "$TOP_README"; then
    echo "ERROR: $fname is not listed in $TOP_README" >&2
    missing=1
  fi
  if ! grep -qF "$fname" "$ARTICLES_README"; then
    echo "ERROR: $fname is not listed in $ARTICLES_README" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  echo "" >&2
  echo "Freshness guard failed: add the article(s) above to the README index/table(s)." >&2
  echo "See CONTRIBUTING.md → 'Article style' and the article table in README.md." >&2
  exit 1
fi

echo "check-readme-articles: OK — all $ARTICLES_DIR/NN-*.md files are indexed in both READMEs."
