#!/bin/sh
# Share a locally running API. Set NGROK_URL for a reserved domain.
set -eu
if [ -n "${NGROK_URL:-}" ]; then
  exec ngrok http "${PORT:-8000}" --url "$NGROK_URL"
fi
exec ngrok http "${PORT:-8000}"
