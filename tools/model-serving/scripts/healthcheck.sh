#!/usr/bin/env bash
set -euo pipefail

service="${1:-}"
port="${2:-}"
host="${3:-127.0.0.1}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env_file="${script_dir}/../.env"
if [[ -f "$env_file" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$env_file"
  set +a
fi

case "$service" in
  vllm)
    port="${port:-${VLLM_PORT:-8000}}"
    ;;
  tei)
    port="${port:-${TEI_PORT:-8080}}"
    ;;
  *)
    echo "usage: $0 {vllm|tei} [port] [host]" >&2
    exit 64
    ;;
esac

url="http://${host}:${port}/health"
if command -v curl >/dev/null 2>&1; then
  curl --fail --silent --show-error "$url" >/dev/null
else
  wget --quiet --spider "$url"
fi

echo "${service} healthy at ${url}"
