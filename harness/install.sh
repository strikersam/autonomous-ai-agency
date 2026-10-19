#!/usr/bin/env bash
# Install the agency harness into another repository.
#
#   harness/install.sh <target-repo> [--link]
#
# Default copies files; --link symlinks them so the target follows this checkout.
# Existing files and folders in the target are never overwritten.
set -euo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-}"
MODE="${2:-copy}"

if [ -z "$TARGET" ] || [ ! -d "$TARGET" ]; then
  echo "usage: $0 <target-repo> [--link]" >&2
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"

place() {
  # place <source> <destination>: copy or link one file/folder, skipping existing ones.
  local src="$1" dst="$2"
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    echo "  skip  ${dst#"$TARGET"/} (exists)"
    return
  fi
  mkdir -p "$(dirname "$dst")"
  if [ "$MODE" = "--link" ]; then
    ln -s "$src" "$dst"
  else
    cp -R "$src" "$dst"
  fi
  echo "  add   ${dst#"$TARGET"/}"
}

echo "Installing agency harness into $TARGET"
for skill in "$HARNESS"/skills/*/; do
  name="$(basename "$skill")"
  place "${skill%/}" "$TARGET/.claude/skills/$name"
  place "${skill%/}" "$TARGET/.agents/skills/$name"
done
for file in "$HARNESS"/agents/*.md; do
  place "$file" "$TARGET/.claude/agents/$(basename "$file")"
done
for file in "$HARNESS"/commands/*.md; do
  place "$file" "$TARGET/.claude/commands/$(basename "$file")"
done
place "$HARNESS/rules/AGENT_RULES.md" "$TARGET/AGENT_RULES.md"

cat <<'EOF'

Done. Next:
  1. Reference AGENT_RULES.md from your CLAUDE.md / AGENTS.md (or paste it in).
  2. Set up MCP connectors: see harness/connectors/README.md.
  3. Restart your agent so it picks up the new skills, subagents and commands.
EOF
