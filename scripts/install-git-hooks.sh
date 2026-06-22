#!/usr/bin/env bash
# install-git-hooks.sh — install the repo's pre-commit hook into .git/hooks.
# Idempotent: re-running overwrites the managed hook. Run once after cloning.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$(git rev-parse --git-path hooks)"
SRC="$REPO_ROOT/scripts/git-hooks/pre-commit"

mkdir -p "$HOOKS_DIR"
cp "$SRC" "$HOOKS_DIR/pre-commit"
chmod +x "$HOOKS_DIR/pre-commit"
echo "Installed pre-commit hook -> $HOOKS_DIR/pre-commit"
echo "It runs scripts/check-readme-articles.sh on every commit (bypass: git commit --no-verify)."
