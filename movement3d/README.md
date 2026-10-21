# movement3d — guide développeur

Module principal du projet **NFL 3D — Prédiction cinématique des déplacements**.
Pour la présentation générale, voir le [README racine](../README.md).

Ce document détaille l'architecture interne, les modules et les paramètres pour
qui veut lire ou étendre le code.

---

## Lancer

```bash
pip install -r requirements.txt

# Dashboard web (http://localhost:8050)
python -m dashboard.app

# Export one-shot (output/prediction_3d.html + .png + README_DELIVERABLE.md)
python main.py

# Tests
python -m pytest tests/ -q
```

Variables d'environnement reconnues (voir `config.py`) :

| Variable      | Défaut        | Rôle |
|---------------|---------------|------|
| `DATA_DIR`    | `../data`     | dossier des CSV |
| `OUTPUT_DIR`  | `output`      | dossier des sorties one-shot |
| `DASH_HOST`   | `0.0.0.0`     | hôte du serveur Dash |
| `DASH_PORT`   | `8050`        | port du serveur Dash |
| `DASH_DEBUG`  | `0`           | mode debug Dash (`1` pour activer) |

---

## Modules

### `config.py`
Constantes centralisées : `DT = 0.1` (10 img/s), `PREDICTION_HORIZON = 20`
(2 s), graine aléatoire, couleurs offense/défense/ballon/surbrillance,
dimensions du terrain, table `TEAM_COLORS` (32 équipes) + `team_color()`,
paramètres du dashboard. Les chemins sont surchargeables par variables d'env.

### `kinematics.py` — le cœur physique (fonctions pures)
- `velocity_components(speed, dir_deg)` → `(vx, vy)` selon la convention NFL
  (0° = +y, sens horaire) : `vx = s·sin(dir)`, `vy = s·cos(dir)`.
- `predict_constant_velocity(...)` → **baseline** sans accélération (`p = p0 + v·t`).
- `predict_trajectory(...)` → modèle à **accélération constante** projetée sur la
  direction du mouvement, borné au terrain.
- `displacement_error(pred, actual)` → distances euclidiennes image par image.
- `ade_fde(pred, actual)` → `(ADE, FDE)` en yards.

### `data_loader.py`
- `load_static_tables()` → dict `{games, plays, players, pffScoutingData}`
  (lève `LoaderFatalError` si un fichier requis manque).
- `load_tracking(game_id, cache=...)` → DataFrame de tracking (ballon marqué
  `is_ball`), `None` si absent.
- `select_pass_play(tables)` → une action de passe par défaut pour le one-shot.

### `analyzer.py`
- `get_play_frames(tracking, play_id)` → images d'une action triées.
- `find_reference_frame(frames, ref_event)` → frame du snap / `pass_forward`
  (avec repli).
- `analyze_play(frames, horizon, dt, ref_event)` → `(results, agg)` :
  par joueur `predicted`, `baseline`, `ade`, `fde`, `ade_baseline` ; agrégats
  `mean_ade`, `mean_fde`, `mean_ade_baseline`, etc.

### `dashboard/`
- `app.py` — layout Dash + tous les callbacks (sélection, scène, fiche joueur,
  insights, recherche).
- `data_catalog.py` — options des menus, recherche joueur, **cache** du tracking
  par match et **index par `playId`** (`get_play_frames`), couleurs d'équipes.
- `scene3d.py` — construit les figures Plotly : `build_animation_figure`
  (slider temporel) et `build_spacetime_figure` (temps en Z). Terrain, end zones,
  lignes, noms, flèches de vitesse, prédiction colorée par erreur, filtre de rôle.
- `player_stats.py` — agrégats d'un joueur sur un match (vitesse, accel,
  distance, ADE/FDE).
- `insights.py` — `ranking_unpredictable()` (plus gros ADE) et
  `error_by_role()` (erreur moyenne par rôle PFF), avec cache par match.
- `assets/style.css` — thème futuriste (néon / glassmorphism), chargé
  automatiquement par Dash.

### `visualizer.py` + `main.py`
Pipeline **one-shot** indépendant du dashboard : sélectionne une action, construit
une figure 3D « espace-temps », l'exporte en HTML + PNG et génère un court README.

---

## Flux de données

```
CSV ──▶ data_loader ──▶ tables
tracking ──▶ data_catalog (cache + index playId) ──▶ play frames
play frames ──▶ analyzer ──▶ kinematics ──▶ results + agg
results ──▶ scene3d / insights ──▶ app.py (Dash)
```

## Notes d'implémentation

- **Déterminisme** : graine fixe, fonctions `kinematics` pures → résultats
  reproductibles (couverts par les tests).
- **Performance** : le tracking (gros fichiers) est chargé une fois par match
  puis indexé par `playId` ; changer d'action est ensuite instantané.
- **Export d'images** : kaleido ≥ 1.0 nécessite Chrome ; le `Dockerfile`
  l'installe via `plotly_get_chrome`. En local, l'absence de Chrome fait sauter
  le PNG sans bloquer le HTML.
