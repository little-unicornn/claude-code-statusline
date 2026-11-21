# claude-code-statusline

A clean status line for [Claude Code](https://claude.com/claude-code), shown below the prompt bar.

```
 Opus 4.8   chase-optimizer
ctx [█████░░░░░░░] 42% · 58% free (420k/1M) │ sess 5h [█████████░░░] 71% · 29% free · reset 19:19 (in 2h) │ weekly [████┃░░░░░░░] 33% · pace 38% (-5) · reset Fri 26 20:49 │ fable [██████████┃░] 92% · pace 38% (+54) · reset Fri 26 20:49 │ ⏱ 1h02m · $1.23
```

## What it shows

1. **Model** + current directory.
2. **Gauges** — each label has its own accent color (ctx = cyan, sess 5h = magenta,
   weekly = blue, per-model = orange), while the bar fill and percentage are
   colored by usage (green < 60%, yellow ≥ 60%, red ≥ 85%) so they double as a
   warning:
   - `ctx` — context window used + tokens.
   - `sess 5h` — rolling 5-hour quota + reset time.
   - `weekly` — weekly quota + reset time.
   - `fable` (or any other per-model weekly limit: opus, sonnet…) + reset time.
   - session duration + cost in USD.

### Weekly pace

The weekly gauges (`weekly` and each per-model limit) carry a `┃` marker at the
point usage would have reached if the quota were spent evenly over the 7-day
window: the window starts 7 days before `resets_at`, and the expected share is
elapsed time / 7 days. The gap in points follows it, `pace 38% (+12)`: green
when at or below pace (up to `PACE_TOLERANCE` points above), yellow beyond,
red beyond twice the tolerance. Set `SHOW_WEEKLY_PACE = False` to hide it.

### Rate-limit snapshot

Every render also writes the `rate_limits` object Claude Code provides to
`~/.cache/claude-code-statusline/rate_limits.json` (with a `written_at`
timestamp), so other local tools can read the current quota without polling
the usage endpoint.

### Per-model limits (Fable…)

Claude Code does not include per-model quotas in the JSON it sends to the status
line, so the script fetches them itself from the claude.ai usage endpoint
(`/api/oauth/usage`) using the OAuth token Claude Code already stores locally
(`~/.claude/.credentials.json`, or the macOS keychain).

The fetch runs in a **detached background process** and the result is cached in
`~/.cache/claude-code-statusline/usage.json` for 60 s, so rendering never waits
on the network. One gauge is shown per model-scoped limit the server reports;
nothing is shown when no such limit exists (API key, Bedrock, Vertex…).
Set `SHOW_MODEL_LIMITS = False` to disable it.

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
- `CTX_COLOR` / `SESSION_COLOR` / `WEEKLY_COLOR` / `MODEL_COLOR` — per-gauge label accent colors.
- `SHOW_MODEL_LIMITS` / `USAGE_TTL` / `USAGE_CACHE` — per-model limit fetching.
- `SHOW_WEEKLY_PACE` / `PACE_TOLERANCE` / `PACE_MARK` — weekly pace marker and gap.
- `SHORTCUTS` — the entries shown by `--keys`.

## Input format

Claude Code sends a JSON object on stdin. Fields used: `model.display_name`,
`workspace.current_dir`, `context_window.*`, `rate_limits.five_hour`,
`rate_limits.seven_day`, `cost.total_cost_usd`, `cost.total_duration_ms`.
All fields are optional — the script never crashes if one is missing.
Per-model limits come from the usage endpoint's `limits[]` entries of kind
`weekly_scoped` (`scope.model.display_name`, `percent`, `resets_at`).

## License

MIT
