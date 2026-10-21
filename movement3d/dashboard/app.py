"""Dashboard interactif 3D de prediction des deplacements NFL.

Permet de :
- selectionner un match (parmi les 122 parties) et une action de passe,
- naviguer dans le temps (slider + play) en mode anime, ou voir les
  trajectoires empilees en mode espace-temps,
- activer/desactiver l'affichage des predictions cinematiques,
- rechercher un joueur et le mettre en surbrillance,
- consulter une fiche de stats agregees du joueur (vitesse, acceleration,
  distance, erreur de prediction) sur le match.

Lancement local :  python -m dashboard.app   (depuis movement3d/)
"""

import os
import sys

from dash import Dash, dcc, html, Input, Output, State, no_update

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config                               # noqa: E402
import analyzer                             # noqa: E402
from dashboard import data_catalog, scene3d, player_stats, insights  # noqa: E402


app = Dash(__name__, title="NFL 3D - Prediction des deplacements")
server = app.server  # pour gunicorn / deploiement


# --------------------------------------------------------------------------
# Composants reutilisables
# --------------------------------------------------------------------------

def _dropdown(id_, placeholder, options=None):
    return dcc.Dropdown(
        id=id_, options=options or [], placeholder=placeholder,
        className="dd", clearable=True,
    )


CONTROLS = html.Div(className="panel", children=[
    html.H3("Contrôles"),

    html.Label("Match"),
    _dropdown("game-dd", "Choisir un match...", data_catalog.game_options()),

    html.Label("Action (passe)"),
    _dropdown("play-dd", "Choisir une action..."),

    html.Label("Joueur (surbrillance)"),
    _dropdown("player-dd", "Choisir un joueur de l'action..."),

    html.Label("Filtre par rôle PFF"),
    dcc.Dropdown(
        id="role-dd", className="dd", clearable=True,
        placeholder="Tous les rôles",
        options=[
            {"label": "Tous les rôles", "value": "all"},
            {"label": "Pass Rush", "value": "Pass Rush"},
            {"label": "Coverage", "value": "Coverage"},
            {"label": "Pass Route", "value": "Pass Route"},
            {"label": "Pass Block", "value": "Pass Block"},
            {"label": "Passer", "value": "Pass"},
        ],
        value="all",
    ),

    html.Hr(),

    html.Label("Mode de visualisation"),
    dcc.RadioItems(
        id="mode-radio",
        options=[
            {"label": " Animation temporelle", "value": "anim"},
            {"label": " Trajectoires espace-temps", "value": "spacetime"},
        ],
        value="anim", className="radio",
    ),

    dcc.Checklist(
        id="pred-check",
        options=[{"label": " Afficher la prédiction cinématique",
                  "value": "show"}],
        value=["show"], className="check",
    ),
    dcc.Checklist(
        id="arrow-check",
        options=[{"label": " Afficher les vecteurs de vitesse",
                  "value": "show"}],
        value=["show"], className="check",
    ),

    html.Label("Image de référence de la prédiction"),
    dcc.RadioItems(
        id="refevent-radio",
        options=[
            {"label": " Snap (ball_snap)", "value": "ball_snap"},
            {"label": " Lancer (pass_forward)", "value": "pass_forward"},
        ],
        value="ball_snap", className="radio",
    ),

    html.Label("Horizon de prédiction"),
    dcc.Slider(
        id="horizon-slider", min=5, max=30, step=5, value=20,
        marks={5: "0.5s", 10: "1s", 15: "1.5s", 20: "2s", 25: "2.5s", 30: "3s"},
    ),

    html.Hr(),

    html.Label("Recherche globale de joueur"),
    dcc.Input(id="player-search", type="text",
              placeholder="Nom du joueur...", debounce=True, className="search"),
    html.Div(id="search-results", className="search-results"),
])


STATS_PANEL = html.Div(className="panel", id="stats-panel", children=[
    html.H3("Fiche joueur"),
    html.Div(id="player-card", children=html.P(
        "Sélectionne un joueur pour voir ses statistiques agrégées sur le match.",
        className="muted")),
])


INSIGHTS_PANEL = html.Div(className="panel", id="insights-panel", children=[
    html.H3("Insights du match"),
    html.Div(className="insights-grid", children=[
        html.Div(children=[
            html.Label("Joueurs les plus imprévisibles (ADE moyen)"),
            html.Div(id="unpredictable-list", children=html.P(
                "Choisis un match pour calculer le classement.", className="muted")),
        ]),
        html.Div(children=[
            html.Label("Erreur de prédiction par rôle PFF"),
            html.Div(id="role-error-list", children=html.P(
                "Choisis un match.", className="muted")),
        ]),
    ]),
])


app.layout = html.Div(className="app", children=[
    html.Div(className="header", children=[
        html.H1("NFL · Dashboard 3D de prédiction des déplacements"),
        html.P("Big Data Bowl 2023 · modèle cinématique (sans ML) · "
               "réel vs prédit en 3D interactive", className="subtitle"),
    ]),
    html.Div(className="layout", children=[
        html.Div(className="sidebar", children=[CONTROLS, STATS_PANEL]),
        html.Div(className="main", children=[
            dcc.Loading(dcc.Graph(id="scene-graph", className="scene",
                                  style={"height": "70vh"}),
                        type="default"),
            html.Div(id="play-meta", className="play-meta"),
            INSIGHTS_PANEL,
        ]),
    ]),
    # Stores pour conserver la selection courante
    dcc.Store(id="store-game"),
    dcc.Store(id="store-play"),
])


# --------------------------------------------------------------------------
# Callbacks
# --------------------------------------------------------------------------

@app.callback(
    Output("play-dd", "options"),
    Output("play-dd", "value"),
    Input("game-dd", "value"),
)
def update_plays(game_id):
    if game_id is None:
        return [], None
    opts = data_catalog.play_options(game_id)
    default = opts[0]["value"] if opts else None
    return opts, default


@app.callback(
    Output("player-dd", "options"),
    Output("player-dd", "value"),
    Input("game-dd", "value"),
    Input("play-dd", "value"),
)
def update_players(game_id, play_id):
    if game_id is None or play_id is None:
        return [], None
    return data_catalog.player_options(game_id, play_id), None


@app.callback(
    Output("scene-graph", "figure"),
    Output("play-meta", "children"),
    Input("game-dd", "value"),
    Input("play-dd", "value"),
    Input("player-dd", "value"),
    Input("mode-radio", "value"),
    Input("pred-check", "value"),
    Input("arrow-check", "value"),
    Input("role-dd", "value"),
    Input("refevent-radio", "value"),
    Input("horizon-slider", "value"),
)
def update_scene(game_id, play_id, player_id, mode, pred_value, arrow_value,
                 role, ref_event, horizon):
    if game_id is None or play_id is None:
        empty = {
            "data": [],
            "layout": {
                "paper_bgcolor": "#1c2541",
                "font": {"color": "white"},
                "annotations": [{
                    "text": "Choisis un match puis une action pour afficher la scène 3D",
                    "showarrow": False, "font": {"size": 18, "color": "white"},
                    "xref": "paper", "yref": "paper", "x": 0.5, "y": 0.5,
                }],
            },
        }
        return empty, ""

    if data_catalog.get_tracking(game_id) is None:
        return no_update, "Fichier de tracking indisponible pour ce match."

    play_frames = data_catalog.get_play_frames(game_id, play_id)
    if play_frames is None or play_frames.empty:
        return no_update, "Aucune donnée de tracking pour cette action."

    play_row = data_catalog.get_play_row(game_id, play_id)
    possession = play_row.get("possessionTeam") if play_row is not None else None
    desc = str(play_row.get("playDescription", "")) if play_row is not None else ""
    show_pred = "show" in (pred_value or [])
    show_arrows = "show" in (arrow_value or [])

    # Noms des joueurs + abreviations d'equipes pour les end zones
    name_map = data_catalog.player_name_map(game_id, play_id)
    home_abbr, away_abbr = data_catalog.game_teams(game_id)
    role_ids = data_catalog.role_nfl_ids(game_id, play_id, role)

    title = f"{desc[:80]}"
    builder = (scene3d.build_animation_figure if mode == "anim"
               else scene3d.build_spacetime_figure)
    fig, agg = builder(
        play_frames, possession, title,
        show_prediction=show_pred, highlight_nfl_id=player_id,
        play_row=play_row, name_map=name_map,
        home_abbr=home_abbr, away_abbr=away_abbr,
        show_arrows=show_arrows, role_ids=role_ids,
        horizon=horizon, ref_event=ref_event)

    # Gain du modele cinematique vs baseline vitesse constante
    gain = agg["mean_ade_baseline"] - agg["mean_ade"]
    gain_txt = (f"−{gain:.2f} yd vs baseline" if gain >= 0
                else f"+{abs(gain):.2f} yd vs baseline")

    meta = html.Div([
        html.Span(f"Possession : {possession}", className="chip"),
        html.Span(f"Joueurs analysés : {agg['n_players']}", className="chip"),
        html.Span(f"ADE : {agg['mean_ade']:.2f} yd", className="chip"),
        html.Span(f"FDE : {agg['mean_fde']:.2f} yd", className="chip"),
        html.Span(f"Baseline (v const.) : {agg['mean_ade_baseline']:.2f} yd",
                  className="chip"),
        html.Span(f"Gain accél. : {gain_txt}", className="chip chip-accent"),
        html.Span(f"Horizon : {agg['horizon']} img "
                  f"({agg['horizon'] * config.DT:.1f}s)", className="chip"),
    ])
    return fig, meta


@app.callback(
    Output("player-card", "children"),
    Input("game-dd", "value"),
    Input("player-dd", "value"),
)
def update_player_card(game_id, player_id):
    if game_id is None or player_id is None:
        return html.P("Sélectionne un joueur pour voir ses statistiques agrégées.",
                      className="muted")
    meta = data_catalog.player_meta(player_id)
    stats = player_stats.aggregate_player(game_id, player_id)
    if meta is None:
        return html.P("Joueur introuvable.", className="muted")

    header = html.Div(className="card-header", children=[
        html.Strong(meta["displayName"]),
        html.Span(f" · {meta['position']}", className="muted"),
    ])
    info = html.Div(className="card-info", children=[
        html.Span(f"Taille {meta['height']}"),
        html.Span(f"Poids {meta['weight']} lb"),
        html.Span(f"{meta['college']}"),
    ])
    if stats is None:
        return html.Div([header, info,
                         html.P("Pas de données de tracking pour ce joueur dans ce match.",
                                className="muted")])

    def stat(label, value, unit=""):
        val = "-" if value != value else f"{value:.2f}{unit}"  # NaN check
        return html.Div(className="stat", children=[
            html.Div(val, className="stat-val"),
            html.Div(label, className="stat-label"),
        ])

    grid = html.Div(className="stat-grid", children=[
        stat("Actions", float(stats["n_plays"])),
        stat("Vitesse max", stats["max_speed"], " yd/s"),
        stat("Vitesse moy.", stats["mean_speed"], " yd/s"),
        stat("Accél. max", stats["max_accel"], " yd/s²"),
        stat("Distance totale", stats["total_distance"], " yd"),
        stat("ADE moyen", stats["mean_ade"], " yd"),
        stat("FDE moyen", stats["mean_fde"], " yd"),
    ])
    return html.Div([header, info, grid])


@app.callback(
    Output("search-results", "children"),
    Input("player-search", "value"),
)
def update_search(query):
    opts = data_catalog.search_players(query)
    if not opts:
        return html.P("Aucun joueur.", className="muted")
    return html.Ul([html.Li(o["label"]) for o in opts], className="search-list")


@app.callback(
    Output("unpredictable-list", "children"),
    Output("role-error-list", "children"),
    Input("game-dd", "value"),
)
def update_insights(game_id):
    if game_id is None:
        msg = html.P("Choisis un match pour calculer les insights.",
                     className="muted")
        return msg, msg

    ranking = insights.ranking_unpredictable(game_id, min_plays=3, top_n=12)
    if not ranking:
        rank_el = html.P("Pas assez de données.", className="muted")
    else:
        rank_el = html.Ol(className="rank-list", children=[
            html.Li([
                html.Span(f"{r['name']} ", className="rank-name"),
                html.Span(f"({r['position']})", className="muted"),
                html.Span(f" {r['mean_ade']:.2f} yd", className="rank-val"),
                html.Span(f" · {r['n_plays']} act.", className="muted"),
            ]) for r in ranking
        ])

    roles = insights.error_by_role(game_id)
    if not roles:
        role_el = html.P("Pas assez de données.", className="muted")
    else:
        role_el = html.Div(className="role-bars", children=[
            html.Div(className="role-row", children=[
                html.Div(r["role"], className="role-name"),
                html.Div(className="role-bar-wrap", children=html.Div(
                    className="role-bar",
                    style={"width": f"{min(100, r['mean_ade'] / 8 * 100):.0f}%"})),
                html.Div(f"{r['mean_ade']:.2f} yd", className="role-val"),
            ]) for r in roles
        ])
    return rank_el, role_el


def main():
    app.run(host=config.DASH_HOST, port=config.DASH_PORT, debug=config.DASH_DEBUG)


if __name__ == "__main__":
    main()
