"""Detección de jugadas de apertura ('Teoría'/book) con la base de datos de Lichess.

Carga los TSV (a-e) de data/openings/ y construye el conjunto de posiciones (EPD)
que aparecen en cualquier línea teórica conocida. Si no hay datos, el llamador
recurre a una heurística de respaldo.
"""
from __future__ import annotations

import csv
from functools import lru_cache

import chess

from .. import config

OPENINGS_DIR = config.DATA_DIR / "openings"


@lru_cache(maxsize=1)
def book_epds() -> frozenset[str]:
    """Conjunto de EPDs (posiciones) que aparecen en la teoría de aperturas."""
    epds: set[str] = set()
    if not OPENINGS_DIR.exists():
        return frozenset()
    for tsv in sorted(OPENINGS_DIR.glob("*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                pgn = (row.get("pgn") or "").strip()
                if not pgn:
                    continue
                board = chess.Board()
                try:
                    for token in pgn.split():
                        if token[0].isdigit():   # ignora "1." "2." ...
                            continue
                        board.push_san(token)
                        epds.add(board.epd())
                except ValueError:
                    continue
    return frozenset(epds)


def available() -> bool:
    return bool(book_epds())


def is_book_position(epd: str) -> bool:
    return epd in book_epds()
