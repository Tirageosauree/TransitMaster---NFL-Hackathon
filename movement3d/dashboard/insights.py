"""Analyses football agregees sur un match entier.

- ranking_unpredictable : classe les joueurs par erreur de prediction moyenne
  (ADE), c.-a-d. les plus "imprevisibles" par le modele cinematique.
- error_by_role : erreur de prediction moyenne par role PFF (pass rush,
  coverage, route, block, passer), pour comparer la previsibilite des roles.

Le calcul parcourt toutes les actions de passe du match, predit chaque joueur
depuis l'image de reference (snap) et mesure l'ecart a la trajectoire reelle.
Les resultats sont mis en cache par gameId pour garder le dashboard reactif.
"""

import os
import sys
import functools

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config          # noqa: E402
import analyzer        # noqa: E402
import kinematics      # noqa: E402
from dashboard import data_catalog  # noqa: E402


@functools.lru_cache(maxsize=8)
def _match_errors(game_id):
    """Calcule, par joueur et par action, l'ADE/FDE sur tout le match.

    Retourne un DataFrame : nflId, playId, ade, fde.
    Cache par gameId (lru_cache) car le calcul est lourd.
    """
    tracking = data_catalog.get_tracking(game_id)
    if tracking is None:
        return pd.DataFrame(columns=["nflId", "playId", "ade", "fde"])

    tables = data_catalog.get_static_tables()
    plays = tables["plays"]
    pass_ids = plays[(plays["gameId"] == game_id) &
                     (plays["passResult"].isin(config.PASS_RESULTS))]["playId"].tolist()

    rows = []
    for play_id in pass_ids:
        play_frames = data_catalog.get_play_frames(game_id, play_id)
        if play_frames is None or play_frames.empty:
            continue
        try:
            results, _ = analyzer.analyze_play(play_frames)
        except Exception:
            continue
        for r in results:
            if r["is_ball"] or np.isnan(r["ade"]):
                continue
            rows.append({"nflId": int(r["nflId"]), "playId": int(play_id),
                         "ade": r["ade"], "fde": r["fde"]})
    return pd.DataFrame(rows)


def ranking_unpredictable(game_id, min_plays=3, top_n=15, most=True):
    """Classement des joueurs par ADE moyen sur le match.

    most=True  -> les plus imprevisibles (ADE le plus eleve).
    most=False -> les plus previsibles (ADE le plus faible).
    Ne garde que les joueurs vus sur >= min_plays actions.
    """
    err = _match_errors(game_id)
    if err.empty:
        return []
    agg = err.groupby("nflId").agg(
        mean_ade=("ade", "mean"),
        mean_fde=("fde", "mean"),
        n_plays=("playId", "nunique"),
    ).reset_index()
    agg = agg[agg["n_plays"] >= min_plays]
    if agg.empty:
        return []
    agg = agg.sort_values("mean_ade", ascending=not most).head(top_n)

    tables = data_catalog.get_static_tables()
    players = tables["players"][["nflId", "displayName", "officialPosition"]]
    agg = agg.merge(players, on="nflId", how="left")

    out = []
    for _, r in agg.iterrows():
        out.append({
            "nflId": int(r["nflId"]),
            "name": r.get("displayName", "Inconnu"),
            "position": r.get("officialPosition", ""),
            "mean_ade": float(r["mean_ade"]),
            "mean_fde": float(r["mean_fde"]),
            "n_plays": int(r["n_plays"]),
        })
    return out


def error_by_role(game_id):
    """Erreur de prediction moyenne (ADE/FDE) par role PFF sur le match."""
    err = _match_errors(game_id)
    if err.empty:
        return []

    tables = data_catalog.get_static_tables()
    pff = tables["pffScoutingData"]
    pff_sub = pff[pff["gameId"] == game_id][["playId", "nflId", "pff_role"]]

    merged = err.merge(pff_sub, on=["playId", "nflId"], how="left")
    merged["pff_role"] = merged["pff_role"].fillna("Inconnu")

    agg = merged.groupby("pff_role").agg(
        mean_ade=("ade", "mean"),
        mean_fde=("fde", "mean"),
        n=("ade", "size"),
    ).reset_index().sort_values("mean_ade", ascending=False)

    out = []
    for _, r in agg.iterrows():
        out.append({
            "role": r["pff_role"],
            "mean_ade": float(r["mean_ade"]),
            "mean_fde": float(r["mean_fde"]),
            "n": int(r["n"]),
        })
    return out
