#!/usr/bin/env bash
# install_git_hooks.sh — pre-commit hook をインストール (demo-static repo 版)
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_DIR="$REPO_ROOT/.git/hooks"
HOOK_FILE="$HOOK_DIR/pre-commit"
if [[ ! -d "$HOOK_DIR" ]]; then echo "[hooks] .git/hooks/ not found" >&2; exit 1; fi
if [[ -f "$HOOK_FILE" ]]; then cp "$HOOK_FILE" "$HOOK_FILE.bak.$(date +%s)"; fi
cat > "$HOOK_FILE" <<'EOF'
#!/usr/bin/env bash
set -e
REPO_ROOT="$(git rev-parse --show-toplevel)"
if [[ -f "$REPO_ROOT/scripts/audit_docs_sensitive.sh" ]]; then
  bash "$REPO_ROOT/scripts/audit_docs_sensitive.sh" --staged
fi
EOF
chmod +x "$HOOK_FILE"
echo "[hooks] installed: $HOOK_FILE"