#!/usr/bin/env bash
set -euo pipefail

# Tail chat-related logs from the app container.
# Requires Docker access and a running docker compose stack.

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if ! command -v docker >/dev/null; then
  echo "docker not found on PATH" >&2
  exit 1
fi

exec docker compose logs -f dragonscales | grep --line-buffered chat_send
