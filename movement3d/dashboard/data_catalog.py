"""Catalogue de donnees pour le dashboard : matchs, actions, joueurs.

Charge les tables statiques une seule fois (singleton) et met en cache les
fichiers de tracking par gameId. Fournit les options des menus deroulants et
les fonctions de recherche de joueurs.
"""

import os
import sys
import functools

import pandas as pd

# Permet d'importer les modules du moteur (config, data_loader, ...) qui sont
# dans le repertoire parent de ce paquet.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config          # noqa: E402
import data_loader     # noqa: E402

# Cache des fichiers de tracking par gameId (charges a la demande)
_TRACKING_CACHE = {}


@functools.lru_cache(maxsize=1)
def get_static_tables():
    """Charge games/plays/players/pff une seule fois."""
    return data_loader.load_static_tables()


def game_options():
    """Options du menu deroulant des matchs.

    Libelle lisible : 'Semaine W - VISITOR @ HOME (date)'.
    """
    tables = get_static_tables()
    games = tables["games"].copy()
    games = games.sort_values(["week", "gameId"])
    options = []
    for _, g in games.iterrows():
        label = (f"S{int(g['week'])} - {g['visitorTeamAbbr']} @ "
                 f"{g['homeTeamAbbr']} ({g['gameDate']})")
        options.append({"label": label, "value": int(g["gameId"])})
    return options


def play_options(game_id):
    """Options du menu deroulant des actions d'un match (passes uniquement)."""
    if game_id is None:
        return []
    tables = get_static_tables()
    plays = tables["plays"]
    sub = plays[(plays["gameId"] == game_id) &
                (plays["passResult"].isin(config.PASS_RESULTS))].copy()
    sub = sub.sort_values("playId")
    options = []
    for _, p in sub.iterrows():
        desc = str(p.get("playDescription", ""))[:70]
        q = p.get("quarter", "?")
        clock = p.get("gameClock", "")
        label = f"Q{q} {clock} - {desc}"
        options.append({"label": label, "value": int(p["playId"])})
    return options


# Index des images par (gameId, playId) pour eviter de re-scanner le gros
# DataFrame de tracking a chaque selection d'action.
_PLAY_INDEX_CACHE = {}


def get_tracking(game_id):
    """Charge (avec cache) le tracking d'un match. None si absent."""
    if game_id is None:
        return None
    return data_loader.load_tracking(game_id, cache=_TRACKING_CACHE)


def get_play_frames(game_id, play_id):
    """Images d'une action, via un index playId -> DataFrame mis en cache.

    Beaucoup plus rapide que de filtrer le tracking complet a chaque appel :
    on construit un groupby par playId une seule fois par match.
    """
    if game_id is None or play_id is None:
        return None
    if game_id not in _PLAY_INDEX_CACHE:
        tracking = get_tracking(game_id)
        if tracking is None:
            return None
        # dict playId -> sous-DataFrame trie par (nflId, frameId)
        idx = {}
        for pid, grp in tracking.groupby("playId"):
            idx[int(pid)] = grp.sort_values(["nflId", "frameId"])
        _PLAY_INDEX_CACHE[game_id] = idx
    return _PLAY_INDEX_CACHE[game_id].get(int(play_id))


def game_teams(game_id):
    """Retourne (home_abbr, away_abbr) pour un match, ou (None, None)."""
    tables = get_static_tables()
    games = tables["games"]
    sub = games[games["gameId"] == game_id]
    if sub.empty:
        return None, None
    g = sub.iloc[0]
    return g.get("homeTeamAbbr"), g.get("visitorTeamAbbr")


def get_play_row(game_id, play_id):
    """Retourne la ligne de plays.csv pour une action donnee (Series ou None)."""
    tables = get_static_tables()
    plays = tables["plays"]
    sub = plays[(plays["gameId"] == game_id) & (plays["playId"] == play_id)]
    if sub.empty:
        return None
    return sub.iloc[0]


def players_in_play(game_id, play_id):
    """Liste des joueurs impliques dans une action, avec leurs noms.

    Retourne une liste de dicts : nflId, displayName, position, team.
    """
    tables = get_static_tables()
    pff = tables["pffScoutingData"]
    players = tables["players"]
    sub = pff[(pff["gameId"] == game_id) & (pff["playId"] == play_id)]
    merged = sub.merge(players, on="nflId", how="left")
    out = []
    for _, r in merged.iterrows():
        out.append({
            "nflId": int(r["nflId"]),
            "displayName": r.get("displayName", "Inconnu"),
            "position": r.get("officialPosition", r.get("pff_positionLinedUp", "")),
            "pff_role": r.get("pff_role", ""),
        })
    return out


def player_options(game_id, play_id):
    """Options du menu deroulant des joueurs d'une action."""
    if game_id is None or play_id is None:
        return []
    opts = []
    for pl in players_in_play(game_id, play_id):
        label = f"{pl['displayName']} ({pl['position']}) - {pl['pff_role']}"
        opts.append({"label": label, "value": pl["nflId"]})
    return sorted(opts, key=lambda o: o["label"])


def search_players(query, limit=25):
    """Recherche globale de joueurs par nom (sur tout players.csv)."""
    tables = get_static_tables()
    players = tables["players"]
    if not query:
        sub = players.head(limit)
    else:
        mask = players["displayName"].str.contains(query, case=False, na=False)
        sub = players[mask].head(limit)
    opts = []
    for _, r in sub.iterrows():
        label = f"{r['displayName']} ({r.get('officialPosition', '')})"
        opts.append({"label": label, "value": int(r["nflId"])})
    return opts


def role_nfl_ids(game_id, play_id, role):
    """Ensemble des nflId ayant un pff_role donne sur une action.

    role == 'all' ou None -> retourne None (pas de filtre).
    """
    if role in (None, "all"):
        return None
    tables = get_static_tables()
    pff = tables["pffScoutingData"]
    sub = pff[(pff["gameId"] == game_id) & (pff["playId"] == play_id) &
              (pff["pff_role"] == role)]
    return set(int(n) for n in sub["nflId"].dropna().tolist())


def player_name_map(game_id, play_id):
    """Dict nflId -> nom court (prenom abrege + nom) pour les etiquettes 3D.

    Exemple : 'Tom Brady' -> 'T.Brady'. Permet d'etiqueter les joueurs
    directement dans la scene sans surcharger l'affichage.
    """
    names = {}
    for pl in players_in_play(game_id, play_id):
        full = str(pl["displayName"])
        parts = full.split()
        if len(parts) >= 2:
            short = f"{parts[0][0]}.{parts[-1]}"
        else:
            short = full
        names[pl["nflId"]] = short
    return names


def player_meta(nfl_id):
    """Metadonnees d'un joueur (nom, position, taille, poids, college)."""
    tables = get_static_tables()
    players = tables["players"]
    sub = players[players["nflId"] == nfl_id]
    if sub.empty:
        return None
    r = sub.iloc[0]
    return {
        "nflId": int(nfl_id),
        "displayName": r.get("displayName", "Inconnu"),
        "position": r.get("officialPosition", ""),
        "height": r.get("height", ""),
        "weight": r.get("weight", ""),
        "college": r.get("collegeName", ""),
    }
