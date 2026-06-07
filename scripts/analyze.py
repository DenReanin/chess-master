"""CLI: analiza partidas con Stockfish y guarda los resultados.

Uso (desde la raíz del proyecto):
    py -m scripts.analyze --limit 1 --depth 14
    py -m scripts.analyze --game-id <url>
"""
from __future__ import annotations

import argparse

from backend import config, db
from backend.engine import analyzer


def main() -> None:
    p = argparse.ArgumentParser(description="Analiza partidas con Stockfish")
    p.add_argument("--limit", type=int, default=1, help="cuántas partidas pendientes procesar")
    p.add_argument("--depth", type=int, default=config.ANALYSIS_DEPTH, help="profundidad de Stockfish")
    p.add_argument("--game-id", default=None, help="analizar una partida concreta por URL")
    p.add_argument("--reanalyze", action="store_true", help="reanalizar aunque ya esté analizada")
    args = p.parse_args()

    if not config.STOCKFISH_PATH:
        raise SystemExit("No se encontró Stockfish en stockfish/. Descárgalo primero.")
    print(f"Usando Stockfish: {config.STOCKFISH_PATH}")

    db.init_db()
    with db.connect() as conn:
        if args.game_id:
            rows = conn.execute("SELECT * FROM games WHERE id = ?", (args.game_id,)).fetchall()
        else:
            where = "" if args.reanalyze else "WHERE analyzed = 0"
            rows = conn.execute(
                f"SELECT * FROM games {where} ORDER BY end_time DESC LIMIT ?", (args.limit,)
            ).fetchall()

        if not rows:
            print("No hay partidas para analizar.")
            return

        for row in rows:
            print(f"\nAnalizando {row['white']} vs {row['black']}  (prof. {args.depth})...")
            result = analyzer.analyze_pgn(row["pgn"], row["user_color"], depth=args.depth)
            db.save_analysis(conn, row["id"], result)
            conn.commit()
            s = result["summary"]
            print(
                f"  imprecisiones={s['inaccuracies']}  errores={s['mistakes']}  "
                f"blunders={s['blunders']}  ACPL={s['acpl']}  precisión={s['accuracy']}%"
            )


if __name__ == "__main__":
    main()
