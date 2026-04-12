#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$REPO_ROOT/.env.nautilus" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env.nautilus"
fi

NAUTILUS_REPO_URL="${NAUTILUS_REPO_URL:-https://github.com/nautechsystems/nautilus_trader.git}"
NAUTILUS_TRADER_TAG="${NAUTILUS_TRADER_TAG:-v1.225.0}"
NAUTILUS_CLONE_DIR="${NAUTILUS_CLONE_DIR:-$REPO_ROOT/tools/nautilus-trader}"

if [[ "$NAUTILUS_CLONE_DIR" != /* ]]; then
  NAUTILUS_CLONE_DIR="$REPO_ROOT/${NAUTILUS_CLONE_DIR#./}"
fi

printf 'Using repo: %s\n' "$NAUTILUS_REPO_URL"
printf 'Using tag: %s\n' "$NAUTILUS_TRADER_TAG"
printf 'Clone dir: %s\n' "$NAUTILUS_CLONE_DIR"

if [[ -d "$NAUTILUS_CLONE_DIR/.git" ]]; then
  printf 'Existing Nautilus clone found. Fetching latest tags...\n'
  git -C "$NAUTILUS_CLONE_DIR" fetch --tags --prune origin
else
  if [[ -e "$NAUTILUS_CLONE_DIR" ]]; then
    printf 'Path exists but is not a git repository: %s\n' "$NAUTILUS_CLONE_DIR" >&2
    exit 1
  fi

  printf 'Cloning NautilusTrader...\n'
  git clone "$NAUTILUS_REPO_URL" "$NAUTILUS_CLONE_DIR"
  git -C "$NAUTILUS_CLONE_DIR" fetch --tags --prune origin
fi

if ! git -C "$NAUTILUS_CLONE_DIR" rev-parse "refs/tags/$NAUTILUS_TRADER_TAG" >/dev/null 2>&1; then
  printf 'Tag not found in repository: %s\n' "$NAUTILUS_TRADER_TAG" >&2
  exit 1
fi

git -C "$NAUTILUS_CLONE_DIR" checkout --force "$NAUTILUS_TRADER_TAG"

PINNED_COMMIT="$(git -C "$NAUTILUS_CLONE_DIR" rev-parse HEAD)"
printf 'NautilusTrader pinned to %s (%s)\n' "$NAUTILUS_TRADER_TAG" "$PINNED_COMMIT"
