#!/usr/bin/env bash
set -euo pipefail

host="${FRONTEND_HOST:-0.0.0.0}"
port="${FRONTEND_PORT:-4173}"
api_base_url="${VITE_API_BASE_URL:-http://localhost:8000}"

cat > /app/frontend/dist/runtime-config.js <<EOF
window.__APP_CONFIG__ = {
  VITE_API_BASE_URL: "${api_base_url}"
};
EOF

exec node /app/docker/frontend-server.mjs
