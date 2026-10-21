"""Tests unitaires du modele cinematique."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import kinematics  # noqa: E402


def test_velocity_components_nfl_convention():
    # dir=0 -> mouvement selon +y (convention NFL)
    vx, vy = kinematics.velocity_components(10.0, 0.0)
    assert abs(vx) < 1e-9
    assert abs(vy - 10.0) < 1e-9

    # dir=90 -> mouvement selon +x
    vx, vy = kinematics.velocity_components(10.0, 90.0)
    assert abs(vx - 10.0) < 1e-9
    assert abs(vy) < 1e-9

    # dir=180 -> -y
    vx, vy = kinematics.velocity_components(5.0, 180.0)
    assert abs(vx) < 1e-9
    assert abs(vy + 5.0) < 1e-9


def test_velocity_norm_equals_speed():
    for d in (0, 37, 90, 211, 359):
        vx, vy = kinematics.velocity_components(7.3, d)
        assert abs(np.hypot(vx, vy) - 7.3) < 1e-9


def test_constant_velocity_straight_line():
    # vitesse 10 yd/s selon +x, dt=0.1, 10 images -> +10 yd en x apres 1s
    pred = kinematics.predict_constant_velocity(50.0, 25.0, 10.0, 90.0, 10, 0.1)
    assert pred.shape == (10, 2)
    # derniere position : x = 50 + 10*1.0 = 60
    assert abs(pred[-1, 0] - 60.0) < 1e-6
    assert abs(pred[-1, 1] - 25.0) < 1e-6


def test_trajectory_with_acceleration_goes_further():
    # a vitesse egale, l'acceleration positive doit mener plus loin
    cv = kinematics.predict_constant_velocity(20.0, 25.0, 5.0, 90.0, 10, 0.1)
    acc = kinematics.predict_trajectory(20.0, 25.0, 5.0, 90.0, 3.0, 10, 0.1)
    assert acc[-1, 0] > cv[-1, 0]


def test_trajectory_clipped_to_field():
    # un joueur au bord qui court vers l'exterieur reste dans le terrain
    pred = kinematics.predict_trajectory(118.0, 2.0, 9.0, 90.0, 5.0, 20, 0.1)
    assert np.all(pred[:, 0] <= 120.0)
    assert np.all(pred[:, 1] >= 0.0)


def test_ade_fde_known_values():
    pred = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
    actual = np.array([[3.0, 4.0], [0.0, 0.0], [6.0, 8.0]])  # dist 5, 0, 10
    ade, fde = kinematics.ade_fde(pred, actual)
    assert abs(ade - 5.0) < 1e-9   # moyenne de 5,0,10
    assert abs(fde - 10.0) < 1e-9  # derniere distance


def test_ade_fde_empty_is_nan():
    ade, fde = kinematics.ade_fde(np.empty((0, 2)), np.empty((0, 2)))
    assert np.isnan(ade) and np.isnan(fde)


def test_displacement_error_truncates_to_min_length():
    pred = np.zeros((5, 2))
    actual = np.array([[3.0, 4.0], [3.0, 4.0]])  # seulement 2 points reels
    errs = kinematics.displacement_error(pred, actual)
    assert len(errs) == 2
    assert np.allclose(errs, 5.0)
