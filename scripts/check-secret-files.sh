#!/usr/bin/env sh
set -eu

staged_files="$(git diff --cached --name-only)"

blocked_patterns='^\.env[^/]*$|^opencode\.json$|^opencode\.fixed\.json$|^auth\.json$|^\.local/share/opencode/|^\.config/opencode/'

if printf '%s\n' "$staged_files" | grep -Eq "$blocked_patterns"; then
  cat >&2 <<'EOF'
Refusing commit: staged OpenCode secret/runtime files detected.

Blocked files:
- .env*
- opencode.json
- opencode.fixed.json
- auth.json
- .local/share/opencode/
- .config/opencode/

Use the checked-in templates or environment examples instead.
EOF
  exit 1
fi

staged_env_files="$(printf '%s\n' "$staged_files" | grep -E '(^|/)\.env(\..+)?$' || true)"
if [ -n "$staged_env_files" ]; then
  for file in $staged_env_files; do
    if git show ":$file" 2>/dev/null | grep -Eq '^(MODEL|AUTH_PROVIDER|API_KEY)='; then
      cat >&2 <<EOF
Refusing commit: staged env file contains OpenCode secret material.

Blocked file:
- $file

Use the checked-in example files instead.
EOF
      exit 1
    fi
  done
fi

exit 0
