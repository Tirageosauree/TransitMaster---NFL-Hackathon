"""Constantes et parametres documentes pour l'outil de prediction 3D."""

import os

# Chemins (surchargeables par variables d'environnement, utile en conteneur)
DATA_DIR = os.environ.get("DATA_DIR", os.path.join("..", "data"))
TRACKING_DIR = os.path.join(DATA_DIR, "tracking")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")
OUTPUT_HTML = os.path.join(OUTPUT_DIR, "prediction_3d.html")
OUTPUT_IMAGE = os.path.join(OUTPUT_DIR, "prediction_3d.png")
OUTPUT_README = os.path.join(OUTPUT_DIR, "README_DELIVERABLE.md")

# Reproductibilite
RANDOM_SEED = 42

# Physique du tracking NFL : 10 images par seconde
DT = 0.1  # secondes par image

# Horizon de prediction (nombre d'images predites apres l'image de reference)
PREDICTION_HORIZON = 20  # 2.0 secondes

# Selection d'action : on predit a partir du snap
SNAP_EVENT = "ball_snap"
PASS_RESULTS = {"C", "I", "S", "IN", "R"}

# Fichiers requis
REQUIRED_FILES = ["games.csv", "plays.csv", "players.csv", "pffScoutingData.csv"]

# Couleurs de la visualisation
COLOR_OFFENSE = "#1f77b4"
COLOR_DEFENSE = "#d62728"
COLOR_BALL = "#8c564b"
COLOR_PREDICTED = "#2ca02c"
COLOR_HIGHLIGHT = "#f1c40f"  # joueur mis en surbrillance

# Dimensions du terrain NFL (yards)
FIELD_LENGTH = 120.0
FIELD_WIDTH = 53.3
ENDZONE_DEPTH = 10.0  # profondeur d'une end zone (yards)

# Couleurs principales des equipes NFL (hex), pour colorer les end zones.
# Valeur par defaut si equipe inconnue : gris fonce.
TEAM_COLORS = {
    "ARI": "#97233F", "ATL": "#A71930", "BAL": "#241773", "BUF": "#00338D",
    "CAR": "#0085CA", "CHI": "#0B162A", "CIN": "#FB4F14", "CLE": "#311D00",
    "DAL": "#003594", "DEN": "#FB4F14", "DET": "#0076B6", "GB": "#203731",
    "HOU": "#03202F", "IND": "#002C5F", "JAX": "#101820", "KC": "#E31837",
    "LA": "#003594", "LAC": "#0080C6", "LV": "#000000", "MIA": "#008E97",
    "MIN": "#4F2683", "NE": "#002244", "NO": "#D3BC8D", "NYG": "#0B2265",
    "NYJ": "#125740", "PHI": "#004C54", "PIT": "#FFB612", "SEA": "#002244",
    "SF": "#AA0000", "TB": "#D50A0A", "TEN": "#0C2340", "WAS": "#5A1414",
}


def team_color(abbr):
    """Couleur principale d'une equipe (hex), gris fonce par defaut."""
    return TEAM_COLORS.get(str(abbr), "#444444")

# Dashboard
DASH_HOST = os.environ.get("DASH_HOST", "0.0.0.0")
DASH_PORT = int(os.environ.get("DASH_PORT", "8050"))
DASH_DEBUG = os.environ.get("DASH_DEBUG", "0") == "1"
