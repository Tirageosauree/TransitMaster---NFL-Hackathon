"""Modele de prediction cinematique (physique, sans ML).

Convention de terrain NFL :
- x = axe long du terrain (0-120 yards, zones d'en-but incluses)
- y = axe court (0-53.3 yards)
- dir = angle de deplacement du joueur en degres (0-360), 0 pointant vers +y,
  mesure dans le sens horaire. On convertit en composantes (vx, vy) via :
      vx = s * sin(radians(dir))
      vy = s * cos(radians(dir))
  (sin/cos inverses par rapport a la convention mathematique standard car la
  reference 0 degre du jeu de donnees pointe selon +y, pas +x.)
"""

import numpy as np


def velocity_components(speed, direction_deg):
    """Convertit (vitesse, direction en degres) en composantes (vx, vy) en yd/s."""
    rad = np.radians(direction_deg)
    vx = speed * np.sin(rad)
    vy = speed * np.cos(rad)
    return vx, vy


def predict_constant_velocity(x0, y0, speed, direction_deg, horizon, dt):
    """Baseline : prediction a VITESSE CONSTANTE (sans acceleration).

    p(t) = p0 + v0 * t. Sert de reference pour mesurer l'apport de la prise
    en compte de l'acceleration dans le modele cinematique complet.
    """
    vx, vy = velocity_components(speed, direction_deg)
    frames = np.arange(1, horizon + 1)
    t = frames * dt
    px = np.clip(x0 + vx * t, 0.0, 120.0)
    py = np.clip(y0 + vy * t, 0.0, 53.3)
    return np.column_stack([px, py])


def predict_trajectory(x0, y0, speed, direction_deg, accel, horizon, dt):
    """Predit les positions futures par integration cinematique.

    Modele a acceleration constante dans la direction du mouvement :
        p(t) = p0 + v0 * t + 0.5 * a * dir_unit * t^2
    L'acceleration est projetee sur le vecteur vitesse unitaire (le joueur
    accelere/decelere principalement le long de sa trajectoire courante).

    Retourne un tableau (horizon, 2) des positions predites aux images
    1..horizon apres l'image de reference.
    """
    vx, vy = velocity_components(speed, direction_deg)

    # Vecteur unitaire de direction du mouvement
    norm = np.hypot(vx, vy)
    if norm > 1e-9:
        ux, uy = vx / norm, vy / norm
    else:
        # Immobile : pas de direction fiable, on reste sur place
        ux, uy = 0.0, 0.0

    ax = accel * ux
    ay = accel * uy

    frames = np.arange(1, horizon + 1)
    t = frames * dt
    px = x0 + vx * t + 0.5 * ax * t ** 2
    py = y0 + vy * t + 0.5 * ay * t ** 2

    # Contrainte terrain : on borne dans les limites physiques du terrain
    px = np.clip(px, 0.0, 120.0)
    py = np.clip(py, 0.0, 53.3)

    return np.column_stack([px, py])


def displacement_error(predicted, actual):
    """Erreur de deplacement euclidienne image par image (en yards).

    predicted, actual : tableaux (k, 2). Retourne un tableau (k,) des distances.
    """
    predicted = np.asarray(predicted, dtype=float)
    actual = np.asarray(actual, dtype=float)
    k = min(len(predicted), len(actual))
    diff = predicted[:k] - actual[:k]
    return np.hypot(diff[:, 0], diff[:, 1])


def ade_fde(predicted, actual):
    """Average Displacement Error et Final Displacement Error (yards)."""
    errors = displacement_error(predicted, actual)
    if len(errors) == 0:
        return float("nan"), float("nan")
    return float(np.mean(errors)), float(errors[-1])
