"""Statistiques agregees d'un joueur sur l'ensemble de ses actions d'un match.

Calcule vitesse max/moyenne, acceleration max, distance totale, et l'erreur de
prediction cinematique moyenne (ADE/FDE) du joueur sur toutes ses actions de
passe du match selectionne.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config          # noqa: E402
import analyzer        # noqa: E402
import kinematics      # noqa: E402
from dashboard import data_catalog  # noqa: E402


def aggregate_player(game_id, nfl_id):
    """Agrege les stats d'un joueur sur toutes ses actions de passe du match.

    Retourne un dict de stats, ou None si aucune donnee.
    """
    tracking = data_catalog.get_tracking(game_id)
    if tracking is None:
        return None

    player_rows = tracking[tracking["nflId"] == nfl_id]
    if player_rows.empty:
        return None

    # Restreindre aux actions de passe du match
    tables = data_catalog.get_static_tables()
    plays = tables["plays"]
    pass_plays = set(
        plays[(plays["gameId"] == game_id) &
              (plays["passResult"].isin(config.PASS_RESULTS))]["playId"].tolist()
    )

    speeds, accels, dists = [], [], []
    ades, fdes = [], []
    n_plays = 0

    for play_id, grp in player_rows.groupby("playId"):
        if play_id not in pass_plays:
            continue
        n_plays += 1
        grp = grp.sort_values("frameId")
        speeds.extend(grp["s"].dropna().tolist())
        accels.extend(grp["a"].dropna().tolist())
        dists.append(float(grp["dis"].fillna(0).sum()))

        # Erreur de prediction du joueur sur cette action
        play_frames = analyzer.get_play_frames(tracking, play_id)
        ref_frame = analyzer.find_reference_frame(play_frames)
        ref_row = grp[grp["frameId"] == ref_frame]
        if ref_row.empty:
            continue
        ref_row = ref_row.iloc[0]
        if np.isnan(ref_row["s"]):
            continue
        predicted = kinematics.predict_trajectory(
            float(ref_row["x"]), float(ref_row["y"]),
            float(ref_row["s"]),
            float(ref_row["dir"]) if not np.isnan(ref_row["dir"]) else 0.0,
            float(ref_row["a"]) if not np.isnan(ref_row["a"]) else 0.0,
            config.PREDICTION_HORIZON, config.DT,
        )
        future = grp[(grp["frameId"] > ref_frame) &
                     (grp["frameId"] <= ref_frame + config.PREDICTION_HORIZON)]
        actual = future[["x", "y"]].to_numpy(dtype=float)
        ade, fde = kinematics.ade_fde(predicted, actual)
        if not np.isnan(ade):
            ades.append(ade)
            fdes.append(fde)

    if n_plays == 0:
        return None

    return {
        "n_plays": n_plays,
        "max_speed": float(np.max(speeds)) if speeds else float("nan"),
        "mean_speed": float(np.mean(speeds)) if speeds else float("nan"),
        "max_accel": float(np.max(accels)) if accels else float("nan"),
        "total_distance": float(np.sum(dists)) if dists else 0.0,
        "mean_ade": float(np.mean(ades)) if ades else float("nan"),
        "mean_fde": float(np.mean(fdes)) if fdes else float("nan"),
    }
