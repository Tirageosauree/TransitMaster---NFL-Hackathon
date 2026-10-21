"""Tests unitaires de l'analyse d'action (sur donnees synthetiques)."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import analyzer  # noqa: E402


def _synthetic_play():
    """Une action minimale : 1 joueur qui avance en ligne droite + ball_snap.

    Le joueur part de (50, 25), vitesse 5 yd/s selon +x (dir=90), accel 0.
    Les positions reelles suivent exactement une vitesse constante, donc la
    prediction cinematique doit avoir une erreur quasi nulle.
    """
    rows = []
    x = 50.0
    for f in range(1, 12):
        event = "ball_snap" if f == 1 else "None"
        rows.append(dict(gameId=1, playId=1, nflId=100, frameId=f,
                         team="AAA", x=x, y=25.0, s=5.0, a=0.0, dir=90.0,
                         event=event, jerseyNumber=10, is_ball=False))
        x += 5.0 * 0.1  # 0.5 yd par image
    return pd.DataFrame(rows)


def test_reference_frame_is_snap():
    pf = _synthetic_play()
    assert analyzer.find_reference_frame(pf, "ball_snap") == 1


def test_reference_frame_fallback_when_event_absent():
    pf = _synthetic_play()
    # pass_forward absent -> repli sur snap
    assert analyzer.find_reference_frame(pf, "pass_forward") == 1


def test_analyze_play_low_error_on_linear_motion():
    pf = _synthetic_play()
    results, agg = analyzer.analyze_play(pf, horizon=10, dt=0.1)
    assert agg["n_players"] == 1
    # mouvement parfaitement lineaire -> erreur quasi nulle
    assert agg["mean_ade"] < 0.05
    # baseline aussi calcule
    assert "mean_ade_baseline" in agg
    assert agg["mean_ade_baseline"] < 0.05


def test_analyze_play_outputs_baseline_and_predicted():
    pf = _synthetic_play()
    results, _ = analyzer.analyze_play(pf, horizon=10, dt=0.1)
    r = results[0]
    assert r["predicted"].shape == (10, 2)
    assert r["baseline"].shape == (10, 2)
    assert not np.isnan(r["ade"])
