#!/usr/bin/env bash
set -euo pipefail

CONFIG_TEMPLATE="${OPENCODE_CONFIG_TEMPLATE:-/home/op/project/opencode.json.template}"
AUTH_TEMPLATE="${OPENCODE_AUTH_TEMPLATE:-/home/op/project/auth.json.template}"

: "${TMF_MCP_URL:?TMF_MCP_URL is required}"
: "${MODEL:=opencode/minimax-m2.5-free}"
: "${AUTH_PROVIDER:=zai-coding-plan}"
: "${API_KEY:=}"

GLOBAL_CONFIG_PATH="${HOME}/.config/opencode/opencode.json"
AUTH_PATH="${HOME}/.local/share/opencode/auth.json"

mkdir -p "$(dirname "$GLOBAL_CONFIG_PATH")"
cp "$CONFIG_TEMPLATE" "$GLOBAL_CONFIG_PATH"

escape() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

sed -i \
  -e "s/__TMF_MCP_URL__/$(escape "$TMF_MCP_URL")/g" \
  -e "s/__OPENCODE_MODEL__/$(escape "$MODEL")/g" \
  "$GLOBAL_CONFIG_PATH"

if [ -f "$AUTH_TEMPLATE" ] && [ -n "$API_KEY" ]; then
  mkdir -p "$(dirname "$AUTH_PATH")"
  cp "$AUTH_TEMPLATE" "$AUTH_PATH"
  sed -i \
    -e "s/__OPENCODE_AUTH_PROVIDER__/$(escape "$AUTH_PROVIDER")/g" \
    -e "s/__OPENCODE_AUTH_KEY__/$(escape "$API_KEY")/g" \
    "$AUTH_PATH"
  echo "Rendered auth config:"
  echo "  - $AUTH_PATH"
fi

echo "Rendered opencode configs:"
echo "  - $GLOBAL_CONFIG_PATH"
