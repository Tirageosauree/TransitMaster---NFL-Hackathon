"""Point d'entree CLI : pipeline complet de prediction 3D des deplacements NFL.

Usage :
    python main.py

Produit :
    output/prediction_3d.html  (visualisation 3D interactive)
    output/prediction_3d.png   (capture statique si kaleido disponible)
    output/README_DELIVERABLE.md
"""

import os
import sys
import random
import numpy as np

import config
import data_loader
import analyzer
import visualizer


def build_readme(agg, play_meta, html_path, image_path):
    """Genere un README de 3 a 5 phrases decrivant la livraison."""
    img_line = os.path.basename(image_path) if image_path else os.path.basename(html_path)
    text = (
        "# Prediction cinematique 3D des deplacements NFL\n\n"
        f"Cet outil predit la trajectoire future de chaque joueur sur une action "
        f"a partir d'un modele cinematique (position, vitesse, acceleration et "
        f"direction au snap, integres a dt=0.1s), sans aucun apprentissage automatique, "
        f"en s'appuyant sur les donnees de tracking et de jeux du NFL Big Data Bowl 2023. "
        f"La visualisation 3D interactive (plotly) affiche le terrain NFL avec le temps "
        f"comme troisieme axe et superpose les trajectoires reelles et predites "
        f"(fichier {img_line}). "
        f"Sur l'action analysee, l'erreur moyenne de deplacement est de "
        f"{agg['mean_ade']:.2f} yards et l'erreur finale de {agg['mean_fde']:.2f} yards "
        f"sur {agg['horizon']} images, revelant ou la physique seule suffit et ou "
        f"l'intention du joueur (coupe, changement de direction) fait diverger la realite. "
        f"Un entraineur, un recruteur ou un commentateur peut l'utiliser pour visualiser "
        f"l'anticipation attendue d'un joueur et reperer les deplacements non lineaires "
        f"les plus difficiles a predire.\n"
    )
    return text


def main():
    random.seed(config.RANDOM_SEED)
    np.random.seed(config.RANDOM_SEED)

    print("[1/5] Chargement des tables statiques...")
    try:
        tables = data_loader.load_static_tables()
    except data_loader.LoaderFatalError as exc:
        print(f"[ERREUR FATALE] {exc}", file=sys.stderr)
        return 1

    print("[2/5] Selection d'une action de passe...")
    game_id, play_id, play_row = data_loader.select_pass_play(tables)
    print(f"        gameId={game_id} playId={play_id}")

    print("[3/5] Chargement du tracking et analyse cinematique...")
    tracking = data_loader.load_tracking(game_id)
    if tracking is None:
        print(f"[ERREUR] Fichier de tracking absent pour gameId={game_id}",
              file=sys.stderr)
        return 1

    play_frames = analyzer.get_play_frames(tracking, play_id)
    if play_frames.empty:
        print("[ERREUR] Aucune image pour cette action", file=sys.stderr)
        return 1

    try:
        results, agg = analyzer.analyze_play(play_frames)
    except Exception as exc:
        print(f"[ERREUR] Echec de l'analyse de l'action : {exc}", file=sys.stderr)
        return 1

    print(f"        {agg['n_players']} joueurs analyses | "
          f"ADE moyen={agg['mean_ade']:.2f} yd, FDE moyen={agg['mean_fde']:.2f} yd")

    print("[4/5] Generation de la visualisation 3D interactive...")
    play_meta = {
        "possession_team": play_row.get("possessionTeam"),
        "defensive_team": play_row.get("defensiveTeam"),
        "description": str(play_row.get("playDescription", "")),
        "game_id": game_id,
        "play_id": play_id,
    }
    fig = visualizer.build_figure(results, agg, play_meta)
    html_path, image_path = visualizer.save_outputs(fig)

    print("[5/5] Generation du README...")
    readme = build_readme(agg, play_meta, html_path, image_path)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(config.OUTPUT_README, "w", encoding="utf-8") as fh:
        fh.write(readme)

    print("\n=== Termine ===")
    print(f"  HTML interactif : {html_path}")
    if image_path:
        print(f"  Image statique  : {image_path}")
    print(f"  README          : {config.OUTPUT_README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
