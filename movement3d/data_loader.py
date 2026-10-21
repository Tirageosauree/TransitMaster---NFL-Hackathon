"""Chargement et jointure des fichiers CSV du jeu de donnees NFL."""

import os
import pandas as pd

import config


class LoaderFatalError(Exception):
    """Erreur fatale de chargement (fichier requis manquant/illisible)."""


def load_static_tables(data_dir=config.DATA_DIR):
    """Charge games/plays/players/pffScoutingData en UTF-8.

    Leve LoaderFatalError si un fichier requis est absent ou illisible.
    Retourne un dict de DataFrames.
    """
    tables = {}
    for fname in config.REQUIRED_FILES:
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            raise LoaderFatalError(f"Fichier requis manquant : {path}")
        try:
            tables[fname.replace(".csv", "")] = pd.read_csv(path, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - cas illisible
            raise LoaderFatalError(f"Fichier illisible {path} : {exc}") from exc
    return tables


def load_tracking(game_id, tracking_dir=config.TRACKING_DIR, cache=None):
    """Charge tracking_[gameId].csv a la demande avec cache optionnel.

    Retourne None si le fichier est absent (non fatal).
    """
    if cache is not None and game_id in cache:
        return cache[game_id]
    path = os.path.join(tracking_dir, f"tracking_{game_id}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, encoding="utf-8")
    df["is_ball"] = df["nflId"].isna()
    if cache is not None:
        cache[game_id] = df
    return df


def select_pass_play(tables):
    """Selectionne une action de passe deterministe pour la demonstration.

    Retourne (game_id, play_id, play_row). Choisit la premiere action de passe
    completee (passResult == 'C') pour un rendu lisible (receveur qui court).
    """
    plays = tables["plays"]
    passes = plays[plays["passResult"].isin(config.PASS_RESULTS)]
    completed = passes[passes["passResult"] == "C"]
    chosen = completed.iloc[0] if len(completed) else passes.iloc[0]
    return int(chosen["gameId"]), int(chosen["playId"]), chosen
