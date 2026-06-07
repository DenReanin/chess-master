"""Descarga de partidas desde la API pública de Chess.com.

API (sin clave): https://www.chess.com/news/view/published-data-api
- Archivos por mes: /pub/player/{usuario}/games/archives
- Cada archivo: lista de partidas con su PGN.
"""
from __future__ import annotations

import re

import httpx

from .. import config, db

BASE = "https://api.chess.com/pub"

# Resultados de Chess.com que significan tablas (el resto: o ganas o pierdes).
DRAW_RESULTS = {
    "agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient",
}

_ECO_RE = re.compile(r'\[ECO\s+"([^"]+)"\]')


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": config.HTTP_USER_AGENT, "Accept": "application/json"},
        timeout=30.0,
        follow_redirects=True,
    )


def list_archives(username: str) -> list[str]:
    with _client() as c:
        r = c.get(f"{BASE}/player/{username.lower()}/games/archives")
        r.raise_for_status()
        return r.json().get("archives", [])


def fetch_archive(url: str) -> list[dict]:
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        return r.json().get("games", [])


def _eco_from_pgn(pgn: str) -> str | None:
    m = _ECO_RE.search(pgn or "")
    return m.group(1) if m else None


def _normalize(game: dict, username: str) -> dict | None:
    """Convierte una partida de la API al formato de nuestra tabla `games`."""
    if game.get("rules") != "chess":  # ignorar variantes (chess960, bughouse...)
        return None
    pgn = game.get("pgn")
    if not pgn:
        return None

    white, black = game.get("white", {}), game.get("black", {})
    uname = username.lower()
    if white.get("username", "").lower() == uname:
        user_color, res = "white", white.get("result")
    elif black.get("username", "").lower() == uname:
        user_color, res = "black", black.get("result")
    else:
        return None

    if res == "win":
        result = "win"
    elif res in DRAW_RESULTS:
        result = "draw"
    else:
        result = "lose"

    return {
        "id": game.get("url"),
        "end_time": game.get("end_time"),
        "time_class": game.get("time_class"),
        "time_control": game.get("time_control"),
        "rated": 1 if game.get("rated") else 0,
        "rules": game.get("rules"),
        "eco": _eco_from_pgn(pgn),
        "eco_url": game.get("eco"),
        "white": white.get("username"),
        "black": black.get("username"),
        "white_rating": white.get("rating"),
        "black_rating": black.get("rating"),
        "result": result,
        "user_color": user_color,
        "pgn": pgn,
    }


def fetch_user_games(
    username: str,
    max_months: int | None = None,
    max_games: int | None = None,
) -> int:
    """Descarga y guarda las partidas del usuario. Devuelve cuántas guardó."""
    db.init_db()
    archives = list_archives(username)
    if max_months:
        archives = archives[-max_months:]  # los meses más recientes

    saved = 0
    with db.connect() as conn:
        for url in archives:
            for raw in fetch_archive(url):
                norm = _normalize(raw, username)
                if norm is None:
                    continue
                db.upsert_game(conn, norm)
                saved += 1
                if max_games and saved >= max_games:
                    conn.commit()
                    return saved
            conn.commit()
    return saved
