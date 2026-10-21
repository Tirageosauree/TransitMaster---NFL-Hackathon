"""Construction des figures 3D plotly pour le dashboard.

Deux modes :
- build_animation_figure : scene 3D animee image par image (slider + play),
  les joueurs se deplacent sur le terrain, le temps = progression de l'action.
- build_spacetime_figure : trajectoires empilees avec le TEMPS en axe Z.

Ameliorations "terrain pro" :
- end zones colorees aux couleurs des equipes, yard lines numerotees,
- ligne de scrimmage et ligne de first down,
- noms des joueurs affiches au-dessus des marqueurs,
- vecteurs de vitesse/orientation (fleches),
- prediction coloree du vert (bonne) au rouge (mauvaise) selon l'erreur.
"""

import os
import sys
import math

import numpy as np
import plotly.graph_objects as go

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config          # noqa: E402
import analyzer        # noqa: E402
import kinematics      # noqa: E402
from dashboard import data_catalog  # noqa: E402


# --------------------------------------------------------------------------
# Couleurs
# --------------------------------------------------------------------------

def _team_color(team, is_ball, possession_team, highlight=False):
    if highlight:
        return config.COLOR_HIGHLIGHT
    if is_ball:
        return config.COLOR_BALL
    if team == possession_team:
        return config.COLOR_OFFENSE
    return config.COLOR_DEFENSE


def _error_color(err, err_max):
    """Couleur vert->jaune->rouge selon l'erreur (0 = vert, err_max = rouge)."""
    if err_max <= 1e-9:
        t = 0.0
    else:
        t = max(0.0, min(1.0, err / err_max))
    # interpolation lineaire sur R et G (vert -> rouge via jaune)
    r = int(255 * min(1.0, 2.0 * t))
    g = int(255 * min(1.0, 2.0 * (1.0 - t)))
    return f"rgb({r},{g},60)"


def _bounds(results, pad=8.0):
    xs, ys = [], []
    for r in results:
        rx, ry = r["ref"]
        xs.append(rx)
        ys.append(ry)
        if len(r["actual"]):
            xs.extend(r["actual"][:, 0])
            ys.extend(r["actual"][:, 1])
        xs.extend(r["predicted"][:, 0])
        ys.extend(r["predicted"][:, 1])
    if not xs:
        return (0, config.FIELD_LENGTH), (0, config.FIELD_WIDTH)
    xmin = max(0.0, min(xs) - pad)
    xmax = min(config.FIELD_LENGTH, max(xs) + pad)
    ymin = max(0.0, min(ys) - pad)
    ymax = min(config.FIELD_WIDTH, max(ys) + pad)
    return (xmin, xmax), (ymin, ymax)


# --------------------------------------------------------------------------
# Terrain
# --------------------------------------------------------------------------

def _grass_surface(xr, yr, z=0.0):
    x = np.linspace(xr[0], xr[1], 2)
    y = np.linspace(yr[0], yr[1], 2)
    xx, yy = np.meshgrid(x, y)
    zz = np.full_like(xx, z)
    return go.Surface(
        x=xx, y=yy, z=zz, showscale=False,
        colorscale=[[0, "#2d5a27"], [1, "#2d5a27"]],
        opacity=0.6, hoverinfo="skip", name="Terrain",
    )


def _endzone_surface(x0, x1, yr, color, z=-0.02):
    """Surface coloree d'une end zone (bande x0..x1), couleur d'equipe."""
    x = np.linspace(x0, x1, 2)
    y = np.linspace(yr[0], yr[1], 2)
    xx, yy = np.meshgrid(x, y)
    zz = np.full_like(xx, z)
    return go.Surface(
        x=xx, y=yy, z=zz, showscale=False,
        colorscale=[[0, color], [1, color]],
        opacity=0.55, hoverinfo="skip", showlegend=False,
    )


def _endzones(xr, yr, home_abbr, away_abbr):
    """Deux end zones colorees si elles sont dans la zone visible."""
    traces = []
    left = (0.0, config.ENDZONE_DEPTH)
    right = (config.FIELD_LENGTH - config.ENDZONE_DEPTH, config.FIELD_LENGTH)
    # end zone gauche = equipe visiteuse, droite = domicile (convention d'affichage)
    if xr[0] < left[1]:
        x0 = max(xr[0], left[0])
        traces.append(_endzone_surface(x0, left[1], yr, config.team_color(away_abbr)))
    if xr[1] > right[0]:
        x1 = min(xr[1], right[1])
        traces.append(_endzone_surface(right[0], x1, yr, config.team_color(home_abbr)))
    return traces


def _yard_lines(xr, yr, z=0.0, numbered=True):
    """Lignes de yard (toutes les 5 yd) + numeros (toutes les 10 yd)."""
    traces = []
    start = int(np.ceil(xr[0] / 5.0) * 5)
    label_x, label_y, label_text = [], [], []
    for xline in range(start, int(xr[1]) + 1, 5):
        traces.append(go.Scatter3d(
            x=[xline, xline], y=[yr[0], yr[1]], z=[z, z],
            mode="lines", line=dict(color="white", width=1.5),
            opacity=0.35, hoverinfo="skip", showlegend=False,
        ))
        # Numero de yard tous les 10 yards (hors end zones)
        if numbered and xline % 10 == 0 and 10 <= xline <= 110:
            # Convertit la coord absolue (0-120) en numero de terrain (0-50-0)
            yard_num = xline - 10
            if yard_num > 50:
                yard_num = 100 - yard_num
            if 0 < yard_num <= 50:
                label_x.append(xline)
                label_y.append(yr[0] + 3)
                label_text.append(str(yard_num))
    if label_text:
        traces.append(go.Scatter3d(
            x=label_x, y=label_y, z=[z + 0.1] * len(label_x),
            mode="text", text=label_text,
            textfont=dict(color="white", size=11),
            hoverinfo="skip", showlegend=False,
        ))
    return traces


def _vertical_line(x, yr, color, name, z_top=1.0, width=5):
    """Ligne verticale sur toute la largeur a une abscisse donnee."""
    return go.Scatter3d(
        x=[x, x], y=[yr[0], yr[1]], z=[0, 0],
        mode="lines", line=dict(color=color, width=width),
        name=name, hoverinfo="name",
    )


def _scrimmage_and_firstdown(play_row, possession_team, xr, yr):
    """Lignes de scrimmage (bleu) et de first down (jaune) si disponibles."""
    traces = []
    if play_row is None:
        return traces
    los = play_row.get("absoluteYardlineNumber")
    to_go = play_row.get("yardsToGo")
    play_dir = None
    try:
        los = float(los)
    except (TypeError, ValueError):
        return traces
    if xr[0] <= los <= xr[1]:
        traces.append(_vertical_line(los, yr, "#1e90ff", "Ligne de scrimmage"))
    # First down : on ne connait pas toujours le sens, on dessine +/- to_go
    try:
        to_go = float(to_go)
        for cand in (los + to_go, los - to_go):
            if xr[0] <= cand <= xr[1]:
                traces.append(_vertical_line(cand, yr, "#f1c40f",
                                             "Ligne de first down", width=4))
                break
    except (TypeError, ValueError):
        pass
    return traces


def _velocity_arrows(sub, possession_team, highlight_nfl_id, scale=0.35,
                     role_ids=None):
    """Fleches de vitesse par joueur (tige + pointe), tracees en lignes.

    Plus propre et lisible que des cones 3D : chaque fleche part du joueur,
    sa longueur est proportionnelle a la vitesse `s`, son orientation suit
    `dir`. On dessine une tige puis deux petits segments formant la pointe.
    Couleur par equipe (offense/defense), jaune si joueur en surbrillance.
    """
    segs_x, segs_y, segs_z, colors = [], [], [], []

    def add_segment(x0, y0, x1, y1, color):
        segs_x.extend([x0, x1, None])
        segs_y.extend([y0, y1, None])
        segs_z.extend([0.03, 0.03, None])
        colors.append(color)

    for _, row in sub.iterrows():
        if bool(row.get("is_ball", False)):
            continue
        if role_ids is not None and int(row["nflId"]) not in role_ids:
            continue
        s = row.get("s", 0.0)
        d = row.get("dir", 0.0)
        if s is None or np.isnan(s) or np.isnan(d) or s < 0.1:
            continue
        hl = (highlight_nfl_id is not None and row["nflId"] == highlight_nfl_id)
        color = _team_color(row["team"], False, possession_team, hl)

        x0, y0 = float(row["x"]), float(row["y"])
        vx, vy = kinematics.velocity_components(float(s), float(d))
        norm = np.hypot(vx, vy)
        if norm < 1e-6:
            continue
        ux, uy = vx / norm, vy / norm
        length = float(s) * scale
        x1, y1 = x0 + ux * length, y0 + uy * length
        add_segment(x0, y0, x1, y1, color)

        # Pointe de fleche : deux petits segments a +/- 150 deg
        head = max(0.25, length * 0.3)
        for ang in (math.radians(150), math.radians(-150)):
            hx = x1 + head * (ux * math.cos(ang) - uy * math.sin(ang))
            hy = y1 + head * (ux * math.sin(ang) + uy * math.cos(ang))
            add_segment(x1, y1, hx, hy, color)

    if not segs_x:
        return None
    # Une seule trace : la couleur de ligne est uniforme, on prend la 1re.
    # (plotly Scatter3d ne colore pas par segment ; on garde un blanc neutre
    #  pour lisibilite sur fond vert, teinte par equipe via opacity.)
    return go.Scatter3d(
        x=segs_x, y=segs_y, z=segs_z, mode="lines",
        line=dict(color="rgba(255,255,255,0.85)", width=3),
        hoverinfo="skip", name="Vecteur vitesse", showlegend=False,
    )


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------

def _scene_layout(title, xr, yr, zlabel, zrange=None):
    yspan = max(yr[1] - yr[0], 1.0)
    xspan = max(xr[1] - xr[0], 1.0)
    axis_bg = "rgba(5, 10, 26, 0.0)"
    grid = "rgba(90, 130, 220, 0.18)"
    scene = dict(
        xaxis=dict(title="x terrain (yd)", range=list(xr), backgroundcolor=axis_bg,
                   color="#8ba0c8", gridcolor=grid, zeroline=False),
        yaxis=dict(title="y terrain (yd)", range=list(yr), backgroundcolor=axis_bg,
                   color="#8ba0c8", gridcolor=grid, zeroline=False),
        zaxis=dict(title=zlabel, backgroundcolor=axis_bg, color="#8ba0c8",
                   gridcolor=grid, zeroline=False),
        aspectmode="manual",
        aspectratio=dict(x=2.0, y=2.0 * yspan / xspan, z=1.0),
        camera=dict(eye=dict(x=1.5, y=-1.8, z=1.0)),
    )
    if zrange is not None:
        scene["zaxis"]["range"] = list(zrange)
    return dict(
        title=dict(text=title, font=dict(color="#eaf2ff", size=16,
                                         family="Orbitron, sans-serif")),
        scene=scene,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#eaf2ff", family="Rajdhani, sans-serif"),
        legend=dict(bgcolor="rgba(8,16,40,0.6)", bordercolor="rgba(90,130,220,0.25)",
                    borderwidth=1),
        margin=dict(l=0, r=0, t=50, b=0),
        uirevision="keep",
    )


def _field_base(xr, yr, play_row, possession_team, home_abbr, away_abbr):
    """Toutes les traces du terrain (herbe, end zones, lignes, numeros)."""
    base = [_grass_surface(xr, yr)]
    base.extend(_endzones(xr, yr, home_abbr, away_abbr))
    base.extend(_yard_lines(xr, yr))
    base.extend(_scrimmage_and_firstdown(play_row, possession_team, xr, yr))
    return base


# --------------------------------------------------------------------------
# Mode 1 : scene animee image par image
# --------------------------------------------------------------------------

def build_animation_figure(play_frames, possession_team, title,
                           show_prediction=True, highlight_nfl_id=None,
                           play_row=None, name_map=None,
                           home_abbr=None, away_abbr=None,
                           show_arrows=True, role_ids=None,
                           horizon=config.PREDICTION_HORIZON,
                           ref_event=config.SNAP_EVENT):
    """Scene 3D animee : chaque image = une frame de l'action.

    Si role_ids est un ensemble de nflId, les joueurs hors de cet ensemble
    sont attenues (gris, transparents) pour faire ressortir le role filtre.
    horizon et ref_event parametrent la prediction (longueur, image de depart).
    """
    results, agg = analyzer.analyze_play(play_frames, horizon=horizon,
                                         ref_event=ref_event)
    xr, yr = _bounds(results)
    ref_frame = agg["ref_frame"]
    horizon = agg["horizon"]
    name_map = name_map or {}

    frame_ids = sorted(
        play_frames[(play_frames["frameId"] >= ref_frame) &
                    (play_frames["frameId"] <= ref_frame + horizon)]["frameId"].unique()
    )
    if not frame_ids:
        frame_ids = sorted(play_frames["frameId"].unique())

    # Position reelle de chaque joueur par offset, pour calculer l'erreur
    pred_by_id = {r["nflId"]: r["predicted"] for r in results if not r["is_ball"]}

    def real_markers(frame_id):
        sub = play_frames[play_frames["frameId"] == frame_id]
        xs, ys, zs, colors, texts, labels = [], [], [], [], [], []
        for _, row in sub.iterrows():
            is_ball = bool(row.get("is_ball", False))
            nid = None if is_ball else int(row["nflId"])
            dimmed = (role_ids is not None and not is_ball and nid not in role_ids)
            hl = (not is_ball) and (highlight_nfl_id is not None and
                                    row["nflId"] == highlight_nfl_id)
            xs.append(row["x"])
            ys.append(row["y"])
            zs.append(0.0)
            if dimmed:
                colors.append("rgba(130,140,160,0.35)")
            else:
                colors.append(_team_color(row["team"], is_ball, possession_team, hl))
            if is_ball:
                texts.append("Ballon")
                labels.append("")
            else:
                texts.append(f"#{row.get('jerseyNumber', '')}")
                # n'etiqueter que les joueurs non attenues pour alleger
                labels.append("" if dimmed else name_map.get(nid, ""))
        return sub, xs, ys, zs, colors, texts, labels

    def predicted_markers(frame_id):
        offset = frame_id - ref_frame
        xs, ys, zs, colors, errs = [], [], [], [], []
        if offset < 1:
            return xs, ys, zs, colors
        # erreurs de l'image courante pour normaliser les couleurs
        cur = {}
        sub = play_frames[play_frames["frameId"] == frame_id].set_index("nflId")
        for nfl_id, pred in pred_by_id.items():
            idx = min(offset, len(pred)) - 1
            if idx < 0 or nfl_id not in sub.index:
                continue
            rx = sub.loc[nfl_id, "x"]
            ry = sub.loc[nfl_id, "y"]
            px, py = pred[idx, 0], pred[idx, 1]
            err = float(np.hypot(px - rx, py - ry))
            cur[nfl_id] = (px, py, err)
        if not cur:
            return xs, ys, zs, colors
        err_max = max(e for _, _, e in cur.values()) or 1.0
        for nfl_id, (px, py, err) in cur.items():
            xs.append(px)
            ys.append(py)
            zs.append(0.0)
            colors.append(_error_color(err, err_max))
        return xs, ys, zs, colors

    def build_frame_data(frame_id):
        data = _field_base(xr, yr, play_row, possession_team, home_abbr, away_abbr)
        sub, xs, ys, zs, colors, texts, labels = real_markers(frame_id)
        # Marqueurs des joueurs (sans texte, pour eviter le chevauchement)
        data.append(go.Scatter3d(
            x=xs, y=ys, z=zs, mode="markers",
            customdata=texts,
            marker=dict(size=6, color=colors, line=dict(color="white", width=1)),
            name="Joueurs (reel)",
            hovertemplate="%{customdata}<br>x=%{x:.1f} y=%{y:.1f}<extra></extra>",
        ))
        # Etiquettes de noms a la position des joueurs (z=0). Le decalage
        # "top center" les place juste au-dessus du marqueur a l'ecran, sans
        # les faire flotter dans la box 3D.
        lxs = [x for x, lb in zip(xs, labels) if lb]
        lys = [y for y, lb in zip(ys, labels) if lb]
        lzs = [0.0 for lb in labels if lb]
        ltx = [lb for lb in labels if lb]
        if ltx:
            data.append(go.Scatter3d(
                x=lxs, y=lys, z=lzs, mode="text",
                text=ltx, textposition="top center",
                textfont=dict(color="white", size=8),
                hoverinfo="skip", showlegend=False,
            ))
        if show_arrows:
            arrows = _velocity_arrows(sub, possession_team, highlight_nfl_id,
                                      role_ids=role_ids)
            if arrows is not None:
                data.append(arrows)
        if show_prediction:
            px, py, pz, pcolors = predicted_markers(frame_id)
            data.append(go.Scatter3d(
                x=px, y=py, z=pz, mode="markers",
                marker=dict(size=5, color=pcolors, symbol="x"),
                name="Predit (vert=bon, rouge=divergent)",
                hovertemplate="Predit<br>x=%{x:.1f} y=%{y:.1f}<extra></extra>",
            ))
        return data

    fig = go.Figure(data=build_frame_data(frame_ids[0]))
    fig.frames = [go.Frame(data=build_frame_data(fid), name=str(fid))
                  for fid in frame_ids]

    steps = [
        dict(method="animate", label=f"{(fid - ref_frame) * config.DT:.1f}s",
             args=[[str(fid)], dict(mode="immediate",
                                    frame=dict(duration=0, redraw=True),
                                    transition=dict(duration=0))])
        for fid in frame_ids
    ]
    # En mode anime la scene est a plat (z=0). On fixe une plage z et on
    # aplatit l'aspect z pour que les marqueurs/noms restent colles au sol.
    layout = _scene_layout(title, xr, yr, zlabel="", zrange=(0.0, 10.0))
    layout["scene"]["zaxis"]["showticklabels"] = False
    layout["scene"]["aspectratio"]["z"] = 0.25
    layout["sliders"] = [dict(active=0, y=0, x=0.1, len=0.9,
                              currentvalue=dict(prefix="t = "), steps=steps)]
    layout["updatemenus"] = [dict(
        type="buttons", showactive=False, y=0, x=0, xanchor="right", yanchor="top",
        buttons=[
            dict(label="Play", method="animate",
                 args=[None, dict(frame=dict(duration=120, redraw=True),
                                  fromcurrent=True, transition=dict(duration=0))]),
            dict(label="Pause", method="animate",
                 args=[[None], dict(mode="immediate",
                                    frame=dict(duration=0, redraw=True),
                                    transition=dict(duration=0))]),
        ],
    )]
    fig.update_layout(layout)
    return fig, agg


# --------------------------------------------------------------------------
# Mode 2 : trajectoires espace-temps (temps en axe Z)
# --------------------------------------------------------------------------

def build_spacetime_figure(play_frames, possession_team, title,
                           show_prediction=True, highlight_nfl_id=None,
                           play_row=None, name_map=None,
                           home_abbr=None, away_abbr=None,
                           role_ids=None, horizon=config.PREDICTION_HORIZON,
                           ref_event=config.SNAP_EVENT, **_):
    """Trajectoires reelles vs predites, le temps etant le 3e axe (Z).

    La prediction est coloree par l'erreur croissante (vert -> rouge).
    Si role_ids est fourni, les joueurs hors role sont attenues.
    """
    results, agg = analyzer.analyze_play(play_frames, horizon=horizon,
                                         ref_event=ref_event)
    xr, yr = _bounds(results)
    name_map = name_map or {}

    fig = go.Figure()
    for t in _field_base(xr, yr, play_row, possession_team, home_abbr, away_abbr):
        fig.add_trace(t)

    legend_seen = set()
    for r in results:
        dimmed = (role_ids is not None and not r["is_ball"] and
                  r["nflId"] not in role_ids)
        hl = (not r["is_ball"]) and (highlight_nfl_id is not None and
                                     r["nflId"] == highlight_nfl_id)
        if dimmed:
            color = "rgba(130,140,160,0.25)"
        else:
            color = _team_color(r["team"], r["is_ball"], possession_team, hl)
        width = 7 if hl else (6 if r["is_ball"] else 4)

        actual = r["actual"]
        if len(actual):
            z = np.arange(1, len(actual) + 1)
            label = "" if r["is_ball"] else name_map.get(r["nflId"], "")
            fig.add_trace(go.Scatter3d(
                x=actual[:, 0], y=actual[:, 1], z=z, mode="lines",
                line=dict(color=color, width=width),
                name="Reel", legendgroup="reel",
                showlegend="reel" not in legend_seen,
                hovertext=label,
                hovertemplate="%{hovertext} Reel<br>x=%{x:.1f} y=%{y:.1f}<br>t=%{z}<extra></extra>",
            ))
            legend_seen.add("reel")

        if show_prediction and not r["is_ball"] and not dimmed:
            pred = r["predicted"]
            k = min(len(pred), len(actual)) if len(actual) else len(pred)
            if k == 0:
                continue
            zp = np.arange(1, k + 1)
            # erreur par image -> couleur
            if len(actual):
                errs = kinematics.displacement_error(pred[:k], actual[:k])
            else:
                errs = np.zeros(k)
            err_max = float(np.max(errs)) if len(errs) else 1.0
            seg_colors = [_error_color(e, err_max) for e in errs]
            fig.add_trace(go.Scatter3d(
                x=pred[:k, 0], y=pred[:k, 1], z=zp, mode="markers+lines",
                line=dict(color=config.COLOR_PREDICTED, width=3, dash="dash"),
                marker=dict(size=3, color=seg_colors),
                opacity=0.85, name="Predit (couleur = erreur)",
                legendgroup="predit", showlegend="predit" not in legend_seen,
                hovertemplate="Predit<br>x=%{x:.1f} y=%{y:.1f}<br>t=%{z}<extra></extra>",
            ))
            legend_seen.add("predit")

    fig.update_layout(_scene_layout(title, xr, yr,
                                    zlabel="temps (images apres snap)"))
    return fig, agg
