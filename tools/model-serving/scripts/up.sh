#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="${MODEL_SERVING_REPO_ROOT:-}"
if [ -z "$repo_root" ]; then
  repo_root="$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null || true)"
fi
compose_file="$repo_root/docker/docker-compose.yml"

command -v docker >/dev/null 2>&1 || fail "Error: docker is not installed or not on PATH."
[ -n "$repo_root" ] || fail "Error: unable to determine the repo root. Set MODEL_SERVING_REPO_ROOT or run the wrapper from inside the repository."
[ -f "$compose_file" ] || fail "Error: compose file not found: $compose_file"
docker compose version >/dev/null 2>&1 || fail "Error: docker compose v2 is not available. Install the Compose plugin and re-run."

runtime_template='{{range $name, $_ := .Runtimes}}{{$name}} {{end}}'
runtime_list="$(
  docker info --format "$runtime_template" 2>/dev/null
)" || fail "Error: docker info failed. Start the Docker daemon and re-run after verifying nvidia-smi on the host."

if ! printf '%s' "$runtime_list" | grep -Eq '(^|[[:space:]])nvidia([[:space:]]|$)'; then
  cat >&2 <<EOF
Error: Docker does not report an NVIDIA runtime.

Remediation:
  1. Confirm the host GPU driver works: nvidia-smi
  2. Install and configure NVIDIA Container Toolkit for Docker
  3. Restart Docker
  4. Verify the runtime with:
     docker info --format '{{range \$name, \$_ := .Runtimes}}{{\$name}} {{end}}'

After that, re-run:
  $0
EOF
  exit 1
fi

exec docker compose -f "$compose_file" up -d
