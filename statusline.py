#!/usr/bin/env python3
"""Status line for Claude Code.

Claude Code sends a JSON describing the session state on stdin.
This script renders two lines below the prompt bar:

  1. model + current directory
  2. gauges: context, 5h session, weekly limit, per-model weekly limits
     (e.g. Fable), duration + cost

Per-model limits are not part of the JSON Claude Code sends, so the script
fetches them itself from the claude.ai usage endpoint with the local OAuth
token, in a detached background process, and renders from a small cache file.
The status line itself never waits on the network.

The keyboard-shortcut cheat sheet is hidden by default. Show it on demand:

  python3 statusline.py --keys

See the README for installation.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

# ─────────────────────────────── ANSI colors ────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"

SEP = f" {DIM}│{RESET} "          # separator between gauges
BAR_WIDTH = 12                    # width of the progress bars

# Color thresholds for gauge fill / percentage (usage % → color)
WARN_PCT = 60
CRIT_PCT = 85

# Per-gauge accent color, applied to the label so each bar is distinguishable.
CTX_COLOR = CYAN
SESSION_COLOR = MAGENTA
WEEKLY_COLOR = BLUE
MODEL_COLOR = "\033[38;5;208m"   # orange (256-color) for per-model limits (Fable…)

# Per-model weekly limits (Fable, Opus, Sonnet…) are fetched from the usage API.
SHOW_MODEL_LIMITS = True
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
USAGE_CACHE = os.path.expanduser("~/.cache/claude-code-statusline/usage.json")
USAGE_TTL = 60          # seconds before a cached value is refreshed
USAGE_TIMEOUT = 5       # seconds for the background HTTP request
CREDENTIALS_FILE = os.path.expanduser("~/.claude/.credentials.json")

# Weekly pace: where usage "should" be now if the quota were spent evenly over
# the 7-day window (rule of three on elapsed time). Shown as a ┃ marker in the
# weekly bars plus the gap in points (+ = ahead of pace, i.e. burning too fast).
SHOW_WEEKLY_PACE = True
WEEK_SECONDS = 7 * 24 * 3600
PACE_MARK = "┃"
PACE_TOLERANCE = 5      # points of gap still shown as "on pace" (green)

# Keyboard-shortcut cheat sheet (shown with `--keys`): (key, label)
SHORTCUTS = [
    [("/branch", "parallel chat"), ("/resume", "other chats"),
     ("Alt+P", "model"), ("/effort", "effort"),
     ("Alt+T", "thinking"), ("/clear", "clear ctx")],
    [("⇧Tab", "autonomy"), ("Ctrl+O", "transcript"),
     ("Ctrl+T", "tasks"), ("Ctrl+B", "background"),
     ("/rewind", "undo"), ("Esc", "interrupt")],
]


# ─────────────────────────────── Formatting ─────────────────────────────────
def human_tokens(n):
    """123456 → '123k' ; 2000000 → '2M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"{n / 1000:.0f}k"
    return str(n)


def human_duration(ms):
    """Milliseconds → '12s' / '3m05s' / '1h02m'."""
    s = int(ms // 1000)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def parse_ts(ts):
    """Unix timestamp or ISO-8601 string → local naive datetime, or None."""
    if not ts:
        return None
    try:
        if isinstance(ts, str) and not ts.lstrip("-").isdigit():
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        return datetime.fromtimestamp(int(ts))
    except (ValueError, OSError, OverflowError):
        return None


def fmt_reset(ts):
    """Unix timestamp / ISO string → readable reset time ('14:30 (in 3h)')."""
    dt = parse_ts(ts)
    if dt is None:
        return "?"
    now = datetime.now()
    delta_h = (dt - now).total_seconds() / 3600
    when = dt.strftime("%H:%M") if dt.date() == now.date() else dt.strftime("%a %d %H:%M")
    if 0 <= delta_h < 24:
        return f"{when} {DIM}(in {delta_h:.0f}h){RESET}"
    return when


# ──────────────────────────── Per-model limits ──────────────────────────────
def oauth_token():
    """Access token Claude Code stores locally (file, or macOS keychain)."""
    try:
        with open(CREDENTIALS_FILE) as f:
            return json.load(f).get("claudeAiOauth", {}).get("accessToken")
    except (OSError, ValueError):
        pass
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["security", "find-generic-password",
                 "-s", "Claude Code-credentials", "-w"],
                capture_output=True, text=True, timeout=3).stdout
            return json.loads(out).get("claudeAiOauth", {}).get("accessToken")
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return None


def write_usage_cache(payload):
    payload["fetched_at"] = time.time()
    os.makedirs(os.path.dirname(USAGE_CACHE), exist_ok=True)
    tmp = f"{USAGE_CACHE}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, USAGE_CACHE)


def refresh_usage():
    """Fetch the usage endpoint and store the per-model limits (background)."""
    token = oauth_token()
    if not token:
        write_usage_cache({"error": "no oauth token"})
        return
    req = urllib.request.Request(USAGE_URL, headers={
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=USAGE_TIMEOUT) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError) as e:
        write_usage_cache({"error": str(e)})
        return
    limits = []
    for lim in data.get("limits") or []:
        model = ((lim.get("scope") or {}).get("model") or {})
        name = model.get("display_name")
        if lim.get("kind") == "weekly_scoped" and name:
            limits.append({"name": name,
                           "pct": lim.get("percent") or 0,
                           "resets_at": lim.get("resets_at")})
    write_usage_cache({"limits": limits})


def load_usage_cache():
    try:
        with open(USAGE_CACHE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def spawn_refresh():
    """Start a detached refresh unless one was started recently."""
    lock = f"{USAGE_CACHE}.lock"
    try:
        if time.time() - os.path.getmtime(lock) < 2 * USAGE_TIMEOUT:
            return
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(USAGE_CACHE), exist_ok=True)
        with open(lock, "w"):
            pass
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--refresh-usage"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def model_limits():
    """Cached per-model limits; triggers a background refresh when stale."""
    if not SHOW_MODEL_LIMITS:
        return []
    cache = load_usage_cache()
    if cache is None or time.time() - cache.get("fetched_at", 0) > USAGE_TTL:
        spawn_refresh()
    return (cache or {}).get("limits") or []


# ─────────────────────────────── Rendering ──────────────────────────────────
def pct_color(pct):
    if pct >= CRIT_PCT:
        return RED
    if pct >= WARN_PCT:
        return YELLOW
    return GREEN


def bar(pct, width=BAR_WIDTH, mark_pct=None, color=""):
    filled = max(0, min(width, int(round(pct / 100 * width))))
    cells = ["█"] * filled + ["░"] * (width - filled)
    if mark_pct is not None:
        i = max(0, min(width - 1, int(mark_pct / 100 * width)))
        cells[i] = f"{RESET}{BOLD}{PACE_MARK}{RESET}{color}"
    return "".join(cells)


def weekly_pace(resets_at):
    """Expected % used right now if spent evenly over the week, or None."""
    if not SHOW_WEEKLY_PACE:
        return None
    end = parse_ts(resets_at)
    if end is None:
        return None
    remaining = (end - datetime.now()).total_seconds()
    elapsed = WEEK_SECONDS - remaining
    if not 0 <= elapsed <= WEEK_SECONDS:
        return None
    return elapsed / WEEK_SECONDS * 100


def pace_text(pct, expected):
    if expected is None:
        return ""
    gap = pct - expected
    if gap > PACE_TOLERANCE:
        c = RED if gap > 2 * PACE_TOLERANCE else YELLOW
    else:
        c = GREEN
    return f" {DIM}· pace {RESET}{expected:.0f}% {c}({gap:+.0f}){RESET}"


def gauge(label, pct, extra="", label_color=DIM, mark_pct=None):
    """Block 'label [████░░░░] NN%'.

    The label uses its per-gauge accent color; the bar and percentage are
    colored by usage (green / yellow / red) so they keep acting as a warning.
    """
    c = pct_color(pct)
    return (f"{label_color}{label}{RESET} {c}[{bar(pct, mark_pct=mark_pct, color=c)}]{RESET} "
            f"{c}{pct:.0f}%{RESET}{extra}")


def render_header(model_name, cwd_short):
    return f"{CYAN}{BOLD} {model_name}{RESET}{DIM}   {cwd_short}{RESET}"


def render_gauges(data):
    parts = []

    ctx = data.get("context_window", {})
    used = ctx.get("used_percentage", 0) or 0
    free = ctx.get("remaining_percentage", 100 - used)
    size = ctx.get("context_window_size", 0) or 0
    tokens = ctx.get("total_input_tokens", 0) or 0
    parts.append(gauge(
        "ctx", used, label_color=CTX_COLOR,
        extra=f" {DIM}· {free:.0f}% free "
              f"({human_tokens(tokens)}/{human_tokens(size)}){RESET}"))

    rl = data.get("rate_limits", {})

    five = rl.get("five_hour", {})
    if five:
        fp = five.get("used_percentage", 0) or 0
        parts.append(gauge(
            "sess 5h", fp, label_color=SESSION_COLOR,
            extra=f" {DIM}· {100 - fp:.0f}% free · reset {RESET}"
                  f"{fmt_reset(five.get('resets_at'))}"))

    week = rl.get("seven_day", {})
    if week:
        wp = week.get("used_percentage", 0) or 0
        exp = weekly_pace(week.get("resets_at"))
        parts.append(gauge(
            "weekly", wp, label_color=WEEKLY_COLOR, mark_pct=exp,
            extra=f"{pace_text(wp, exp)} {DIM}· reset {RESET}"
                  f"{fmt_reset(week.get('resets_at'))}"))

    for lim in model_limits():
        exp = weekly_pace(lim.get("resets_at"))
        parts.append(gauge(
            lim["name"].lower(), lim["pct"], label_color=MODEL_COLOR, mark_pct=exp,
            extra=f"{pace_text(lim['pct'], exp)} {DIM}· reset {RESET}"
                  f"{fmt_reset(lim.get('resets_at'))}"))

    cost = data.get("cost", {})
    total_cost = cost.get("total_cost_usd", 0) or 0
    duration = cost.get("total_duration_ms", 0) or 0
    parts.append(f"{DIM}⏱ {human_duration(duration)} · ${total_cost:.2f}{RESET}")

    return SEP.join(parts)


def render_shortcuts():
    def fmt(row):
        return "  ".join(f"{CYAN}{key}{RESET} {DIM}{label}{RESET}" for key, label in row)
    return [f"{DIM}⌨{RESET}  " + fmt(SHORTCUTS[0]),
            "   " + fmt(SHORTCUTS[1])]


# ─────────────────────────── Rate limits snapshot ───────────────────────────
RATE_LIMITS_FILE = os.path.expanduser("~/.cache/claude-code-statusline/rate_limits.json")


def save_rate_limits(data):
    """Drop the rate_limits Claude Code hands us into a file, for the cockpit.

    Free: no network call, unlike the usage endpoint (which answers 429 as
    soon as it is polled). Fresh whenever a session is rendering — which is
    exactly when the quota moves.
    """
    rl = data.get("rate_limits")
    if not rl:
        return
    try:
        os.makedirs(os.path.dirname(RATE_LIMITS_FILE), exist_ok=True)
        tmp = f"{RATE_LIMITS_FILE}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump({"rate_limits": rl, "written_at": time.time()}, f)
        os.replace(tmp, RATE_LIMITS_FILE)
    except OSError:
        pass


# ─────────────────────────────── Entry point ────────────────────────────────
def main():
    # `--keys` / `keys`: print the shortcut cheat sheet and exit.
    if any(a in ("--keys", "-k", "keys") for a in sys.argv[1:]):
        print("\n".join(render_shortcuts()))
        return
    # `--refresh-usage`: background worker that updates the usage cache.
    if "--refresh-usage" in sys.argv[1:]:
        refresh_usage()
        return

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}

    save_rate_limits(data)

    model = data.get("model", {})
    model_name = model.get("display_name", model.get("id", "?"))

    workspace = data.get("workspace", {})
    cwd = workspace.get("current_dir") or data.get("cwd") or os.getcwd()
    cwd_short = os.path.basename(cwd.rstrip("/")) or cwd

    print(render_header(model_name, cwd_short))
    print(render_gauges(data))


if __name__ == "__main__":
    main()
