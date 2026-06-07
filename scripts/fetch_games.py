"""CLI: descarga tus partidas de Chess.com a la base de datos local.

Uso (desde la raíz del proyecto):
    py -m scripts.fetch_games --months 3
    py -m scripts.fetch_games --max 10
"""
from __future__ import annotations

import argparse

from backend import config
from backend.ingest import chesscom


def main() -> None:
    p = argparse.ArgumentParser(description="Descarga partidas de Chess.com")
    p.add_argument("--user", default=config.CHESSCOM_USERNAME, help="usuario de Chess.com")
    p.add_argument("--months", type=int, default=None, help="solo los N meses más recientes")
    p.add_argument("--max", type=int, default=None, help="máximo de partidas a guardar")
    args = p.parse_args()

    if not args.user:
        raise SystemExit("Define CHESSCOM_USERNAME en .env o pasa --user.")

    print(f"Descargando partidas de '{args.user}'...")
    n = chesscom.fetch_user_games(args.user, max_months=args.months, max_games=args.max)
    print(f"Guardadas {n} partidas en {config.DB_PATH}")


if __name__ == "__main__":
    main()
