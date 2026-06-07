"""CLI: genera el comentario del entrenador (Gemini) para una partida analizada.

Uso (desde la raíz del proyecto):
    py -m scripts.coach            # la última partida analizada
    py -m scripts.coach --game-id <url>
"""
from __future__ import annotations

import argparse

from backend import config, db
from backend.coach import gemini


def _load_analysis(conn, game_id: str) -> dict:
    moves = conn.execute(
        "SELECT * FROM moves WHERE game_id = ? ORDER BY ply", (game_id,)
    ).fetchall()
    summary = conn.execute(
        "SELECT * FROM game_summary WHERE game_id = ?", (game_id,)
    ).fetchone()
    return {"moves": [dict(m) for m in moves], "summary": dict(summary)}


def main() -> None:
    p = argparse.ArgumentParser(description="Comentario de entrenador con Gemini")
    p.add_argument("--game-id", default=None, help="URL de la partida (por defecto: la última analizada)")
    args = p.parse_args()

    if not config.GEMINI_API_KEY:
        raise SystemExit("Falta GEMINI_API_KEY en .env")

    with db.connect() as conn:
        if args.game_id:
            game = conn.execute("SELECT * FROM games WHERE id = ?", (args.game_id,)).fetchone()
        else:
            game = conn.execute(
                "SELECT * FROM games WHERE analyzed = 1 ORDER BY end_time DESC LIMIT 1"
            ).fetchone()
        if not game:
            raise SystemExit("No hay partidas analizadas. Ejecuta antes scripts.analyze.")

        analysis = _load_analysis(conn, game["id"])
        print(f"Generando comentario para {game['white']} vs {game['black']}...\n")
        note = gemini.coach_game(dict(game), analysis)
        db.save_coach_note(conn, game["id"], note)
        conn.commit()

    print("=" * 60)
    print(note)
    print("=" * 60)


if __name__ == "__main__":
    main()
