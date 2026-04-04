#!/usr/bin/env bash
set -euo pipefail

/home/op/project/scripts/render-opencode-runtime.sh
exec opencode serve --hostname 0.0.0.0
