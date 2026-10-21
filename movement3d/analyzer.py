"""Analyse d'une action : prediction cinematique + erreurs, par joueur."""

import numpy as np

import config
import kinematics


def get_play_frames(tracking_df, play_id):
    """Extrait et trie les images d'une action donnee."""
    play = tracking_df[tracking_df["playId"] == play_id].copy()
    return play.sort_values(["nflId", "frameId"])


def find_reference_frame(play_frames, ref_event=config.SNAP_EVENT):
    """Retourne le frameId de l'evenement de reference.

    ref_event : 'ball_snap' (defaut) ou 'pass_forward' (ballon en l'air), etc.
    Repli : si l'evenement est absent, on prend le snap ; a defaut la 1re image.
    """
    ev = play_frames[play_frames["event"] == ref_event]
    if len(ev):
        return int(ev["frameId"].min())
    snaps = play_frames[play_frames["event"] == config.SNAP_EVENT]
    if len(snaps):
        return int(snaps["frameId"].min())
    return int(play_frames["frameId"].min())


def analyze_play(play_frames, horizon=config.PREDICTION_HORIZON, dt=config.DT,
                 ref_event=config.SNAP_EVENT):
    """Pour chaque joueur, predit la trajectoire depuis l'image de reference.

    Retourne (results, agg) :
    - results : liste de dicts par joueur (nflId, team, is_ball, ref(x,y),
      actual (k,2), predicted (horizon,2), baseline (horizon,2), ade, fde,
      ade_baseline).
    - agg : stats agregees (ADE/FDE moyens cinematique et baseline).
    """
    ref_frame = find_reference_frame(play_frames, ref_event)
    results = []

    for nfl_id, grp in play_frames.groupby("nflId", dropna=False):
        grp = grp.sort_values("frameId")
        ref_row = grp[grp["frameId"] == ref_frame]
        if ref_row.empty:
            continue
        ref_row = ref_row.iloc[0]

        x0, y0 = float(ref_row["x"]), float(ref_row["y"])
        speed = float(ref_row["s"]) if not np.isnan(ref_row["s"]) else 0.0
        direction = float(ref_row["dir"]) if not np.isnan(ref_row["dir"]) else 0.0
        accel = float(ref_row["a"]) if not np.isnan(ref_row["a"]) else 0.0

        predicted = kinematics.predict_trajectory(
            x0, y0, speed, direction, accel, horizon, dt
        )
        baseline = kinematics.predict_constant_velocity(
            x0, y0, speed, direction, horizon, dt
        )

        # Trajectoire reelle : images de reference+1 a reference+horizon
        future = grp[(grp["frameId"] > ref_frame) &
                     (grp["frameId"] <= ref_frame + horizon)]
        actual = future[["x", "y"]].to_numpy(dtype=float)

        ade, fde = kinematics.ade_fde(predicted, actual)
        ade_base, _ = kinematics.ade_fde(baseline, actual)

        results.append({
            "nflId": nfl_id,
            "team": ref_row["team"],
            "is_ball": bool(ref_row.get("is_ball", False)),
            "ref": (x0, y0),
            "actual": actual,
            "predicted": predicted,
            "baseline": baseline,
            "ade": ade,
            "fde": fde,
            "ade_baseline": ade_base,
            "ref_frame": ref_frame,
        })

    valid = [r for r in results if not np.isnan(r["ade"])]
    valid_base = [r for r in results if not np.isnan(r["ade_baseline"])]
    agg = {
        "mean_ade": float(np.mean([r["ade"] for r in valid])) if valid else float("nan"),
        "mean_fde": float(np.mean([r["fde"] for r in valid])) if valid else float("nan"),
        "mean_ade_baseline": (float(np.mean([r["ade_baseline"] for r in valid_base]))
                              if valid_base else float("nan")),
        "n_players": len(valid),
        "horizon": horizon,
        "ref_frame": ref_frame,
        "ref_event": ref_event,
    }
    return results, agg
