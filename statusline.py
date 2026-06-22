#!/usr/bin/env python3
"""Status line pour Claude Code.

Claude Code envoie sur stdin un JSON décrivant l'état de la session.
Ce script en tire 4 lignes affichées sous la barre de prompt :

  1. modèle + dossier courant
  2. jauges : contexte, session 5 h, limite hebdo, durée + coût
  3. aide-mémoire raccourcis (1/2)
  4. aide-mémoire raccourcis (2/2)

Installation : voir le README.
"""
import json
import os
import sys
from datetime import datetime

# ─────────────────────────────── Couleurs ANSI ──────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

SEP = f" {DIM}│{RESET} "          # séparateur entre jauges
BAR_WIDTH = 12                    # largeur des barres de progression

# Seuils de couleur des jauges (% d'usage → couleur)
WARN_PCT = 60
CRIT_PCT = 85

# Raccourcis affichés sur les lignes 3 et 4 : (touche, libellé)
SHORTCUTS = [
    [("/branch", "disc. parallèle"), ("/resume", "autres disc."),
     ("Alt+P", "modèle"), ("/effort", "intensité"),
     ("Alt+T", "thinking"), ("/clear", "vider ctx")],
    [("⇧Tab", "autonomie"), ("Ctrl+O", "transcript"),
     ("Ctrl+T", "tâches"), ("Ctrl+B", "background"),
     ("/rewind", "annuler"), ("Esc", "interrompre")],
]


# ─────────────────────────────── Formatage ──────────────────────────────────
def human_tokens(n):
    """123456 → '123k' ; 2000000 → '2M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"{n / 1000:.0f}k"
    return str(n)


def human_duration(ms):
    """Millisecondes → '12s' / '3m05s' / '1h02m'."""
    s = int(ms // 1000)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def fmt_reset(ts):
    """Timestamp unix → heure de remise à zéro lisible ('14:30 (dans 3h)')."""
    if not ts:
        return "?"
    try:
        dt = datetime.fromtimestamp(int(ts))
    except (ValueError, OSError, OverflowError):
        return "?"
    now = datetime.now()
    delta_h = (dt - now).total_seconds() / 3600
    when = dt.strftime("%H:%M") if dt.date() == now.date() else dt.strftime("%a %d %H:%M")
    if 0 <= delta_h < 24:
        return f"{when} {DIM}(dans {delta_h:.0f}h){RESET}"
    return when


# ─────────────────────────────── Rendu ──────────────────────────────────────
def pct_color(pct):
    if pct >= CRIT_PCT:
        return RED
    if pct >= WARN_PCT:
        return YELLOW
    return GREEN


def bar(pct, width=BAR_WIDTH):
    filled = max(0, min(width, int(round(pct / 100 * width))))
    return "█" * filled + "░" * (width - filled)


def gauge(label, pct, extra=""):
    """Bloc 'label [████░░░░] NN%' coloré selon le taux d'usage."""
    c = pct_color(pct)
    return f"{DIM}{label}{RESET} {c}[{bar(pct)}]{RESET} {c}{pct:.0f}%{RESET}{extra}"


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
        "ctx", used,
        extra=f" {DIM}· {free:.0f}% libre "
              f"({human_tokens(tokens)}/{human_tokens(size)}){RESET}"))

    rl = data.get("rate_limits", {})

    five = rl.get("five_hour", {})
    if five:
        fp = five.get("used_percentage", 0) or 0
        parts.append(gauge(
            "sess 5h", fp,
            extra=f" {DIM}· {100 - fp:.0f}% libre · reset {RESET}"
                  f"{fmt_reset(five.get('resets_at'))}"))

    week = rl.get("seven_day", {})
    if week:
        wp = week.get("used_percentage", 0) or 0
        parts.append(gauge(
            "hebdo", wp,
            extra=f" {DIM}· reset {RESET}{fmt_reset(week.get('resets_at'))}"))

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


# ─────────────────────────────── Entrée ─────────────────────────────────────
def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}

    model = data.get("model", {})
    model_name = model.get("display_name", model.get("id", "?"))

    workspace = data.get("workspace", {})
    cwd = workspace.get("current_dir") or data.get("cwd") or os.getcwd()
    cwd_short = os.path.basename(cwd.rstrip("/")) or cwd

    lines = [render_header(model_name, cwd_short), render_gauges(data)]
    lines += render_shortcuts()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
