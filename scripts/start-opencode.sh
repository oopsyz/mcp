#!/usr/bin/env bash
set -euo pipefail

/home/op/project/scripts/bootstrap-runtime.sh
exec opencode serve --hostname 0.0.0.0 --port 4096
