# claude-code-statusline

A clean status line for [Claude Code](https://claude.com/claude-code), shown below the prompt bar.

```
 Opus 4.8   chase-optimizer
ctx [█████░░░░░░░] 42% · 58% free (420k/1M) │ sess 5h [█████████░░░] 71% · 29% free · reset 19:19 (in 2h) │ weekly [████░░░░░░░░] 33% · reset Fri 26 20:49 │ ⏱ 1h02m · $1.23
```

## What it shows

1. **Model** + current directory.
2. **Gauges** — each label has its own accent color (ctx = cyan, sess 5h = magenta,
   weekly = blue), while the bar fill and percentage are colored by usage
   (green < 60%, yellow ≥ 60%, red ≥ 85%) so they double as a warning:
   - `ctx` — context window used + tokens.
   - `sess 5h` — rolling 5-hour quota + reset time.
   - `weekly` — weekly quota + reset time.
   - session duration + cost in USD.

## Keyboard cheat sheet

The shortcut cheat sheet is **hidden by default** to keep the status line compact.
Show it on demand:

```bash
python3 ~/.claude/statusline.py --keys
```

```
⌨  /branch parallel chat  /resume other chats  Alt+P model  /effort effort  Alt+T thinking  /clear clear ctx
   ⇧Tab autonomy  Ctrl+O transcript  Ctrl+T tasks  Ctrl+B background  /rewind undo  Esc interrupt
```

## Installation

```bash
git clone git@github.com:little-unicornn/claude-code-statusline.git
cd claude-code-statusline
./install.sh
```

`install.sh` copies the script to `~/.claude/statusline.py` and enables `statusLine`
in `~/.claude/settings.json` (existing settings are preserved). Or do it by hand:

```bash
cp statusline.py ~/.claude/statusline.py
```

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py",
    "padding": 0
  }
}
```

Requirements: Python 3 (no external dependencies), a terminal with ANSI color and UTF-8.

## Customization

Everything is at the top of `statusline.py`:

- `WARN_PCT` / `CRIT_PCT` — gauge color thresholds.
- `BAR_WIDTH` — bar width.
- `CTX_COLOR` / `SESSION_COLOR` / `WEEKLY_COLOR` — per-gauge label accent colors.
- `SHORTCUTS` — the entries shown by `--keys`.

## Input format

Claude Code sends a JSON object on stdin. Fields used: `model.display_name`,
`workspace.current_dir`, `context_window.*`, `rate_limits.five_hour`,
`rate_limits.seven_day`, `cost.total_cost_usd`, `cost.total_duration_ms`.
All fields are optional — the script never crashes if one is missing.

## License

MIT
