#!/bin/sh
# Emit runtime config from VITE_* env vars into /env.js.
# Loaded by index.html before the app bundle.
set -eu

ENV_JS=/usr/share/nginx/html/env.js
API_BASE="${VITE_API_BASE:-/api}"
WS_BASE="${VITE_WS_BASE:-/ws}"

cat > "$ENV_JS" <<EOF
window.ANDUIN_CONFIG = {
  API_BASE: "$API_BASE",
  WS_BASE: "$WS_BASE"
};
EOF

echo "[entrypoint] env.js: API_BASE=$API_BASE WS_BASE=$WS_BASE"
