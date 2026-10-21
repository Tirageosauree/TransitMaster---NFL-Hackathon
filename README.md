# 🏈 NFL 3D — Prédiction cinématique des déplacements

> Dashboard 3D interactif qui **prédit les déplacements des joueurs NFL** par un modèle
> **cinématique pur (sans machine learning)** et confronte la prédiction à la réalité,
> image par image, sur un terrain rendu en 3D.
>
> Réalisé pour le hackathon **NFL Big Data Bowl 2023** (données NFL Next Gen Stats + PFF).

---

## 🎯 En une phrase

À partir de la position, la vitesse, l'accélération et la direction d'un joueur à un
instant donné (le snap ou le lancer), on extrapole sa trajectoire sur les 2 prochaines
secondes avec les lois de la physique, puis on mesure **où et quand la physique
décroche** — c'est-à-dire là où l'intention humaine (coupes, réactions) prend le pas sur
l'inertie.

## 💡 Pourquoi c'est intéressant (lecture football)

Le modèle cinématique prédit **presque parfaitement les joueurs de ligne** (ils bougent
peu, de façon prévisible) mais **échoue sur les receveurs** qui cassent leurs routes.
Cette divergence, mesurée en yards, devient une **métrique de « imprévisibilité »** :

| Rôle PFF        | Erreur moyenne (ADE) | Lecture |
|-----------------|----------------------|---------|
| Pass Route      | ~2.3 yd              | le plus imprévisible (coupes, doubles-moves) |
| Pass Rush       | ~1.5 yd              | trajectoires plus directes |
| Coverage        | ~1.3 yd              | réactif mais contraint |
| Pass Block      | ~1.0 yd              | le plus prévisible (peu de déplacement) |

*(valeurs indicatives sur un match ; recalculées en direct dans le dashboard)*

C'est une grille de lecture directement exploitable par un **entraîneur** (qui casse bien
sa route ?), un **recruteur** (profil athlétique vs. réactif) ou un **commentateur**
(visualiser l'anticipation attendue).

---

## ✨ Fonctionnalités

### Visualisation
- **Terrain NFL 3D réaliste** : yard lines numérotées, end zones aux couleurs des équipes,
  ligne de scrimmage (bleu) et ligne de first down (jaune).
- **Deux modes** : animation image par image (slider + Play), ou trajectoires empilées
  avec le **temps en 3ᵉ axe**.
- **Noms des joueurs** affichés directement sur le terrain.
- **Vecteurs de vitesse** (flèches) par joueur, orientés selon `dir`, longueur ∝ vitesse.
- **Prédiction colorée par erreur** : du vert (bonne prédiction) au rouge (divergence).

### Analyse & interactivité
- Sélection **match → action → joueur** par menus déroulants, plus recherche globale.
- **Filtre par rôle PFF** (pass rush, coverage, route, block, passer) qui isole un groupe.
- **Horizon de prédiction réglable** (0,5 s → 3 s) par slider.
- **Image de référence configurable** : prédire depuis le snap ou depuis le lancer.
- **Fiche joueur** : vitesse max/moyenne, accélération max, distance, ADE/FDE sur le match.
- **Insights du match** : classement des joueurs les plus imprévisibles + erreur par rôle.
- **Baseline comparative** : modèle « vitesse constante » vs cinématique complet, pour
  chiffrer l'apport de l'accélération.

---

## 🧮 Le modèle (physique, sans ML)

Pour chaque joueur, à partir de l'image de référence :

```
v = (s·sin(dir), s·cos(dir))          # vitesse → composantes (convention NFL)
p(t) = p0 + v·t + ½·a·û·t²            # accélération projetée sur la direction
```

avec `dt = 0,1 s` (tracking à 10 images/s). La trajectoire prédite est bornée aux limites
du terrain (0–120 × 0–53,3 yd).

**Métriques d'erreur** (en yards) :
- **ADE** (Average Displacement Error) : erreur moyenne sur l'horizon.
- **FDE** (Final Displacement Error) : erreur à la dernière image prédite.

`FDE > ADE` signale que l'erreur s'accumule avec le temps — la signature de l'intention
qui diverge de l'inertie.

---

## 🚀 Démarrage rapide

### Avec Docker (recommandé)

Depuis la racine du projet :

```bash
docker compose up --build dashboard
# puis ouvrir http://localhost:8050
```

### En local

```bash
cd movement3d
pip install -r requirements.txt
python -m dashboard.app
# puis ouvrir http://localhost:8050
```

> Sur Windows, utilisez le lanceur `py` au lieu de `python` si besoin.

### Export one-shot (sans dashboard)

Génère une capture 3D d'une action (HTML interactif + PNG + README court) :

```bash
# local
cd movement3d && python main.py
# ou Docker
docker compose run --rm render
```

Sorties dans `movement3d/output/`.

---

## 🧪 Tests

```bash
cd movement3d
python -m pytest tests/ -q
```

12 tests unitaires couvrent la conversion vitesse→vecteur (convention NFL), le modèle
baseline, l'apport de l'accélération, le clipping terrain, le calcul ADE/FDE et la
détection de l'image de référence.

---

## 🗂️ Structure du projet

```
.
├── docker-compose.yml          # services "dashboard" (web) et "render" (one-shot)
├── data/                       # jeu de données NFL Big Data Bowl 2023 (CSV)
│   └── DATASET.md              # documentation des données (NFL + PFF)
└── movement3d/
    ├── Dockerfile              # image Python + Chrome (kaleido) + gunicorn
    ├── requirements.txt
    ├── config.py               # constantes : dt, horizon, graine, couleurs d'équipes
    ├── kinematics.py           # physique : vitesse→vecteur, intégration, baseline, ADE/FDE
    ├── data_loader.py          # chargement/jointure des CSV
    ├── analyzer.py             # prédiction par joueur + erreurs sur une action
    ├── visualizer.py           # figure 3D one-shot (pipeline main.py)
    ├── main.py                 # export one-shot HTML/PNG/README
    ├── tests/                  # tests unitaires (pytest)
    └── dashboard/              # application Dash
        ├── app.py              # layout + callbacks
        ├── data_catalog.py     # matchs / actions / joueurs + cache + index par playId
        ├── scene3d.py          # figures 3D (animation + espace-temps, terrain, flèches)
        ├── player_stats.py     # stats agrégées d'un joueur sur un match
        ├── insights.py         # classement imprévisibles + erreur par rôle
        └── assets/style.css    # thème futuriste (néon / glassmorphism)
```

---

## 🏗️ Architecture

```
                 ┌──────────────┐
   CSV data ───▶ │ data_loader  │ ──▶ tables (games/plays/players/pff)
                 └──────────────┘
                 ┌──────────────┐
   tracking ───▶ │ data_catalog │ ──▶ cache + index par playId
                 └──────┬───────┘
                        │ play frames
                 ┌──────▼───────┐     ┌──────────────┐
                 │   analyzer   │ ──▶ │  kinematics  │  (prédiction + baseline)
                 └──────┬───────┘     └──────────────┘
         results + agg  │
                 ┌──────▼───────┐     ┌──────────────┐
                 │   scene3d    │     │   insights   │
                 └──────┬───────┘     └──────┬───────┘
                        │  figures           │ classements
                 ┌──────▼────────────────────▼───────┐
                 │          dashboard/app.py          │  (Dash + callbacks)
                 └────────────────────────────────────┘
```

- **Déterministe** : graine fixe, calculs purs, résultats reproductibles.
- **Performant** : tracking mis en cache par match, puis indexé par `playId` (lookups
  instantanés après le premier chargement).
- **Portable** : tout tourne en conteneur, données montées en volume.

---

## 🛠️ Stack technique

- **Python 3.12**
- **pandas / numpy** — traitement des données et calcul vectoriel
- **Plotly** — rendu 3D interactif
- **Dash** — application web
- **gunicorn** — serveur WSGI (production)
- **kaleido + Chrome** — export d'images statiques
- **pytest** — tests unitaires
- **Docker / Docker Compose** — conteneurisation

---

## 📊 Données

NFL Big Data Bowl 2023 (saison 2021, semaines 1–8) : 122 matchs, tracking image par image
(position, vitesse, accélération, orientation) + scouting PFF (rôles, pressions, blocs).
Voir [`data/DATASET.md`](data/DATASET.md) pour le détail des colonnes.

Source : <https://github.com/ThompsonJamesBliss/nfl-big-data-bowl-regional-event-data>

---

## 📄 Licence & crédits

Projet réalisé dans le cadre du hackathon AWS × NFL Big Data Bowl 2023. Données NFL Next
Gen Stats et Pro Football Focus, à usage de la compétition.
