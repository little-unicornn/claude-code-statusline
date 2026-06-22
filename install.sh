#!/usr/bin/env bash
# Installe la status line dans ~/.claude et l'active dans settings.json.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/statusline.py"
DEST="$HOME/.claude/statusline.py"
SETTINGS="$HOME/.claude/settings.json"

mkdir -p "$HOME/.claude"
cp "$SRC" "$DEST"
echo "✓ copié → $DEST"

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
print(f"✓ statusLine activée dans {path}")
PY

echo "Terminé. Relance Claude Code pour voir la status line."
