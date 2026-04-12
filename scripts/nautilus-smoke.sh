#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$REPO_ROOT/.env.nautilus" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env.nautilus"
fi

NAUTILUS_CLONE_DIR="${NAUTILUS_CLONE_DIR:-$REPO_ROOT/tools/nautilus-trader}"

if [[ "$NAUTILUS_CLONE_DIR" != /* ]]; then
  NAUTILUS_CLONE_DIR="$REPO_ROOT/${NAUTILUS_CLONE_DIR#./}"
fi

if [[ ! -d "$NAUTILUS_CLONE_DIR/.git" ]]; then
  printf 'Nautilus clone not found at %s\n' "$NAUTILUS_CLONE_DIR" >&2
  printf 'Run ./scripts/bootstrap-nautilus.sh first.\n' >&2
  exit 1
fi

cd "$REPO_ROOT"
docker compose -f docker/docker-compose.nautilus.yml run --rm nautilus
