#!/usr/bin/env bash
# test-check-readme-articles.sh — fixture test for the README-freshness guard.
# Proves: (1) the current repo passes, (2) an unlisted article makes it FAIL.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
CHECK="$REPO_ROOT/scripts/check-readme-articles.sh"

pass=0
fail=0
ok()   { echo "  PASS: $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL: $1"; fail=$((fail+1)); }

echo "Case 1: current repo state passes the guard"
if bash "$CHECK" >/dev/null 2>&1; then ok "guard exits 0 on a fully-indexed repo"; else bad "guard rejected a clean repo"; fi

echo "Case 2: an unlisted article makes the guard fail"
FIXTURE="$REPO_ROOT/docs/articles/99-fixture-unlisted-$$.md"
cleanup() { rm -f "$FIXTURE"; }
trap cleanup EXIT
printf -- '---\ntitle: "Fixture"\n---\n# Fixture\n' > "$FIXTURE"
if bash "$CHECK" >/dev/null 2>&1; then
  bad "guard passed despite an unlisted article (99-fixture)"
else
  ok "guard exits non-zero when an article is missing from the index"
fi
cleanup
trap - EXIT

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
