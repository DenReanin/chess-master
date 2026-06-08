"""Entrenamiento táctico: ejercicios generados desde los errores del usuario.

Cada ejercicio es una posición justo ANTES de un error tuyo (blunder/error/
oportunidad perdida); la solución es la mejor jugada según Stockfish.
"""
from __future__ import annotations

from .. import db


def get_puzzles(limit: int = 20) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT m.fen_before, m.best_uci, m.best_san, m.san, m.classification,
                      m.move_number, m.eval_cp, g.white, g.black, g.user_color
               FROM moves m JOIN games g ON g.id = m.game_id
               WHERE m.is_user_move = 1
                 AND m.classification IN ('blunder', 'mistake', 'miss')
                 AND m.best_uci IS NOT NULL AND m.fen_before IS NOT NULL
               ORDER BY m.winprob_drop DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    puzzles = []
    for r in rows:
        fen = r["fen_before"]
        opp = r["black"] if r["user_color"] == "white" else r["white"]
        puzzles.append({
            "fen": fen,
            "side_to_move": fen.split(" ")[1] if fen else "w",
            "solution_uci": r["best_uci"],
            "solution_san": r["best_san"],
            "played_san": r["san"],
            "classification": r["classification"],
            "move_number": r["move_number"],
            "eval_cp": r["eval_cp"],
            "opponent": opp,
        })
    return puzzles
