#!/usr/bin/env bash
# Install the status line into ~/.claude and enable it in settings.json.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/statusline.py"
DEST="$HOME/.claude/statusline.py"
SETTINGS="$HOME/.claude/settings.json"

mkdir -p "$HOME/.claude"
cp "$SRC" "$DEST"
echo "✓ copied → $DEST"

python3 - "$SETTINGS" <<'PY'
import json, os, sys
path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {}
data["statusLine"] = {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py",
    "padding": 0,
}
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"✓ statusLine enabled in {path}")
PY

echo "Done. Restart Claude Code to see the status line."
echo "Tip: run 'python3 ~/.claude/statusline.py --keys' for the shortcut cheat sheet."
