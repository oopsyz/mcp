#!/usr/bin/env bash
set -euo pipefail

CONFIG_TEMPLATE="${OPENCODE_CONFIG_TEMPLATE:-/home/op/project/opencode.sidecar.json.template}"
AUTH_TEMPLATE="${OPENCODE_AUTH_TEMPLATE:-/home/op/project/auth.sidecar.json.template}"

: "${MODEL:?MODEL is required}"
: "${AUTH_PROVIDER:?AUTH_PROVIDER is required}"
: "${API_KEY:?API_KEY is required}"

GLOBAL_CONFIG_PATH="${HOME}/.config/opencode/opencode.json"
AUTH_PATH="${HOME}/.local/share/opencode/auth.json"

mkdir -p "$(dirname "$GLOBAL_CONFIG_PATH")" "$(dirname "$AUTH_PATH")"
cp "$CONFIG_TEMPLATE" "$GLOBAL_CONFIG_PATH"
cp "$AUTH_TEMPLATE" "$AUTH_PATH"

escape() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

sed -i \
  -e "s/__OPENCODE_MODEL__/$(escape "$MODEL")/g" \
  "$GLOBAL_CONFIG_PATH"

sed -i \
  -e "s/__OPENCODE_AUTH_PROVIDER__/$(escape "$AUTH_PROVIDER")/g" \
  -e "s/__OPENCODE_AUTH_KEY__/$(escape "$API_KEY")/g" \
  "$AUTH_PATH"

echo "Rendered opencode runtime config:"
echo "  - $GLOBAL_CONFIG_PATH"
echo "  - $AUTH_PATH"
