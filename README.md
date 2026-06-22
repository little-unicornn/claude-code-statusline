# claude-code-statusline

Status line à 4 lignes pour [Claude Code](https://claude.com/claude-code), affichée sous la barre de prompt.

![lignes affichées](#) <!-- ajoute une capture si tu veux -->

```
 Opus 4.8   chase-optimizer
ctx [█████░░░░░░░] 42% · 58% libre (420k/1M) │ sess 5h [█████████░░░] 71% · 29% libre · reset 19:19 (dans 2h) │ hebdo [████░░░░░░░░] 33% · reset Fri 26 20:49 │ ⏱ 1h02m · $1.23
⌨  /branch disc. parallèle  /resume autres disc.  Alt+P modèle  /effort intensité  Alt+T thinking  /clear vider ctx
   ⇧Tab autonomie  Ctrl+O transcript  Ctrl+T tâches  Ctrl+B background  /rewind annuler  Esc interrompre
```

## Ce qui est affiché

1. **Modèle** + dossier courant.
2. **Jauges** colorées (vert < 60 %, jaune ≥ 60 %, rouge ≥ 85 %) :
   - `ctx` — fenêtre de contexte utilisée + tokens.
   - `sess 5h` — quota de la fenêtre glissante de 5 h + heure de reset.
   - `hebdo` — quota hebdomadaire + heure de reset.
   - durée de session + coût en $.
3. & 4. **Aide-mémoire** des raccourcis Claude Code.

## Installation

```bash
git clone git@github.com:little-unicornn/claude-code-statusline.git
cp claude-code-statusline/statusline.py ~/.claude/statusline.py
```

Puis ajoute dans `~/.claude/settings.json` :

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py",
    "padding": 0
  }
}
```

Ou laisse le script faire la copie + la config :

```bash
./install.sh
```

Prérequis : Python 3 (aucune dépendance externe). Un terminal qui supporte les couleurs ANSI et l'UTF-8.

## Personnalisation

Tout est en haut de `statusline.py` :

- `WARN_PCT` / `CRIT_PCT` — seuils de couleur des jauges.
- `BAR_WIDTH` — largeur des barres.
- `SHORTCUTS` — les raccourcis affichés sur les lignes 3 et 4.

## Format d'entrée

Claude Code envoie un JSON sur stdin. Champs utilisés : `model.display_name`,
`workspace.current_dir`, `context_window.*`, `rate_limits.five_hour`,
`rate_limits.seven_day`, `cost.total_cost_usd`, `cost.total_duration_ms`.
Tous les champs sont optionnels — le script ne plante pas si l'un manque.

## Licence

MIT
