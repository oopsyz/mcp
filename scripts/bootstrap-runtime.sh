#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${TMF_MCP_URL:?TMF_MCP_URL is required}"
: "${MODEL:=opencode/minimax-m2.5-free}"
: "${AUTH_PROVIDER:=zai-coding-plan}"
: "${API_KEY:=}"

if [ ! -f "${OPENCODE_CONFIG_TEMPLATE:-$SCRIPT_DIR/../opencode.json.template}" ]; then
  echo "Config template not found: ${OPENCODE_CONFIG_TEMPLATE:-$SCRIPT_DIR/../opencode.json.template}" >&2
  exit 1
fi

if [ ! -f "${OPENCODE_AUTH_TEMPLATE:-$SCRIPT_DIR/../auth.json.template}" ]; then
  echo "Auth template not found: ${OPENCODE_AUTH_TEMPLATE:-$SCRIPT_DIR/../auth.json.template}" >&2
  exit 1
fi

export OPENCODE_CONFIG_TEMPLATE="${OPENCODE_CONFIG_TEMPLATE:-$SCRIPT_DIR/../opencode.json.template}"
export OPENCODE_AUTH_TEMPLATE="${OPENCODE_AUTH_TEMPLATE:-$SCRIPT_DIR/../auth.json.template}"

"$SCRIPT_DIR/render-opencode-runtime.sh"
