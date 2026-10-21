"""Visualisation 3D interactive (plotly) : terrain NFL + trajectoires reelles vs predites.

Le 3e axe (z) represente le TEMPS (image apres l'image de reference), ce qui
permet de voir les trajectoires se derouler dans l'espace-temps. On distingue :
- offense (bleu), defense (rouge), ballon (orange) pour les trajectoires reelles ;
- predictions cinematiques en pointilles verts.
"""

import os
import numpy as np
import plotly.graph_objects as go

import config


def _play_bounds(results, pad=8.0):
    xs, ys = [], []
    for r in results:
        rx, ry = r["ref"]
        xs.append(rx); ys.append(ry)
        if len(r["actual"]):
            xs.extend(r["actual"][:, 0]); ys.extend(r["actual"][:, 1])
        xs.extend(r["predicted"][:, 0]); ys.extend(r["predicted"][:, 1])
    xmin, xmax = max(0.0, min(xs) - pad), min(120.0, max(xs) + pad)
    ymin, ymax = max(0.0, min(ys) - pad), min(53.3, max(ys) + pad)
    return (xmin, xmax), (ymin, ymax)


def _field_surface(xr, yr):
    x = np.linspace(xr[0], xr[1], 2)
    y = np.linspace(yr[0], yr[1], 2)
    xx, yy = np.meshgrid(x, y)
    zz = np.zeros_like(xx)
    return go.Surface(
        x=xx, y=yy, z=zz, showscale=False,
        colorscale=[[0, "#2d5a27"], [1, "#2d5a27"]],
        opacity=0.65, hoverinfo="skip", name="Terrain",
    )


def _yard_lines(xr, yr):
    traces = []
    start = int(np.ceil(xr[0] / 5.0) * 5)
    for xline in range(start, int(xr[1]) + 1, 5):
        traces.append(go.Scatter3d(
            x=[xline, xline], y=[yr[0], yr[1]], z=[0, 0],
            mode="lines", line=dict(color="white", width=1.5),
            opacity=0.35, hoverinfo="skip", showlegend=False,
        ))
    return traces


def _team_color(team, is_ball, possession_team):
    if is_ball:
        return config.COLOR_BALL
    if team == possession_team:
        return config.COLOR_OFFENSE
    return config.COLOR_DEFENSE


def _legend_proxies(possession_team, defensive_team):
    def proxy(name, color, dash=None):
        return go.Scatter3d(
            x=[None], y=[None], z=[None], mode="lines",
            line=dict(color=color, width=6, dash=dash),
            name=name, showlegend=True,
        )
    return [
        proxy(f"Offense reel ({possession_team})", config.COLOR_OFFENSE),
        proxy(f"Defense reel ({defensive_team})", config.COLOR_DEFENSE),
        proxy("Ballon reel", config.COLOR_BALL),
        proxy("Predit (cinematique)", config.COLOR_PREDICTED, dash="dash"),
    ]


def build_figure(results, agg, play_meta):
    fig = go.Figure()
    xr, yr = _play_bounds(results)
    fig.add_trace(_field_surface(xr, yr))
    for t in _yard_lines(xr, yr):
        fig.add_trace(t)

    possession = play_meta.get("possession_team")
    defense = play_meta.get("defensive_team")
    for p in _legend_proxies(possession, defense):
        fig.add_trace(p)

    for r in results:
        color = _team_color(r["team"], r["is_ball"], possession)
        actual = r["actual"]
        predicted = r["predicted"]

        if len(actual):
            z_actual = np.arange(1, len(actual) + 1)
            fig.add_trace(go.Scatter3d(
                x=actual[:, 0], y=actual[:, 1], z=z_actual,
                mode="lines",
                line=dict(color=color, width=6 if r["is_ball"] else 5),
                showlegend=False,
                hovertemplate="Reel<br>x=%{x:.1f} y=%{y:.1f}<br>t=%{z} img<extra></extra>",
            ))

        z_pred = np.arange(1, len(predicted) + 1)
        fig.add_trace(go.Scatter3d(
            x=predicted[:, 0], y=predicted[:, 1], z=z_pred,
            mode="lines",
            line=dict(color=config.COLOR_PREDICTED, width=4, dash="dash"),
            opacity=0.8, showlegend=False,
            hovertemplate="Predit<br>x=%{x:.1f} y=%{y:.1f}<br>t=%{z} img<extra></extra>",
        ))

        rx, ry = r["ref"]
        fig.add_trace(go.Scatter3d(
            x=[rx], y=[ry], z=[0], mode="markers",
            marker=dict(size=7 if r["is_ball"] else 5, color=color,
                        symbol="diamond" if r["is_ball"] else "circle",
                        line=dict(color="white", width=1)),
            showlegend=False,
            hovertemplate=f"{r['team']}<br>depart x=%{{x:.1f}} y=%{{y:.1f}}<extra></extra>",
        ))

    title = (
        f"Prediction cinematique 3D des deplacements NFL<br>"
        f"<sub>{play_meta.get('description', '')[:85]} | "
        f"ADE={agg['mean_ade']:.2f} yd, FDE={agg['mean_fde']:.2f} yd "
        f"sur {agg['horizon']} images ({agg['horizon']*config.DT:.1f}s)</sub>"
    )
    xspan = max(xr[1] - xr[0], 1.0)
    yspan = max(yr[1] - yr[0], 1.0)
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis=dict(title="x terrain (yards)", range=list(xr), backgroundcolor="#0b132b"),
            yaxis=dict(title="y terrain (yards)", range=list(yr), backgroundcolor="#0b132b"),
            zaxis=dict(title="temps (images apres snap)", backgroundcolor="#0b132b"),
            aspectmode="manual",
            aspectratio=dict(x=2.0, y=2.0 * yspan / xspan, z=1.0),
            camera=dict(eye=dict(x=1.5, y=-1.8, z=1.0)),
        ),
        paper_bgcolor="#1c2541",
        font=dict(color="white"),
        legend=dict(bgcolor="rgba(0,0,0,0.4)", font=dict(size=13)),
        margin=dict(l=0, r=0, t=80, b=0),
    )
    return fig


def save_outputs(fig, html_path=config.OUTPUT_HTML, image_path=config.OUTPUT_IMAGE):
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    fig.write_html(html_path, include_plotlyjs="cdn")
    image_written = False
    try:
        fig.write_image(image_path, width=1400, height=800, scale=2)
        image_written = True
    except Exception as exc:
        print(f"[info] Image statique non generee (kaleido requis) : {exc}")
    return html_path, (image_path if image_written else None)
