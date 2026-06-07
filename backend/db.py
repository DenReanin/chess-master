"""Capa de base de datos (SQLite): partidas, jugadas analizadas y resúmenes."""
from __future__ import annotations

import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id            TEXT PRIMARY KEY,   -- URL única de la partida en Chess.com
    end_time      INTEGER,
    time_class    TEXT,
    time_control  TEXT,
    rated         INTEGER,
    rules         TEXT,
    eco           TEXT,
    eco_url       TEXT,
    white         TEXT,
    black         TEXT,
    white_rating  INTEGER,
    black_rating  INTEGER,
    result        TEXT,               -- resultado para el usuario: win/lose/draw
    user_color    TEXT,               -- white/black
    pgn           TEXT,
    fetched_at    TEXT DEFAULT (datetime('now')),
    analyzed      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS moves (
    game_id        TEXT,
    ply            INTEGER,
    move_number    INTEGER,
    color          TEXT,
    san            TEXT,
    uci            TEXT,
    fen_before     TEXT,
    fen_after      TEXT,       -- posición resultante (para navegar el tablero)
    eval_cp        INTEGER,    -- evaluación (perspectiva de las blancas) tras la jugada real
    best_uci       TEXT,
    best_san       TEXT,
    cp_loss        INTEGER,    -- pérdida en centipawns (perspectiva del que mueve)
    winprob_drop   REAL,       -- caída de probabilidad de victoria (0..1)
    classification TEXT,       -- best/good/inaccuracy/mistake/blunder
    is_user_move   INTEGER,
    PRIMARY KEY (game_id, ply)
);

CREATE TABLE IF NOT EXISTS game_summary (
    game_id      TEXT PRIMARY KEY,
    inaccuracies INTEGER,
    mistakes     INTEGER,
    blunders     INTEGER,
    acpl         REAL,    -- pérdida media de centipawns del usuario
    accuracy     REAL,    -- precisión estimada (0..100)
    coach_note   TEXT     -- comentario del entrenador (LLM), opcional
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn, table: str, column: str, decl: str) -> None:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Migraciones suaves para bases de datos creadas antes de añadir columnas.
        _ensure_column(conn, "moves", "fen_after", "TEXT")


def upsert_game(conn: sqlite3.Connection, game: dict) -> None:
    """Inserta/actualiza una partida preservando el flag 'analyzed' si ya existía."""
    conn.execute(
        """INSERT OR REPLACE INTO games
        (id, end_time, time_class, time_control, rated, rules, eco, eco_url,
         white, black, white_rating, black_rating, result, user_color, pgn, analyzed)
        VALUES
        (:id, :end_time, :time_class, :time_control, :rated, :rules, :eco, :eco_url,
         :white, :black, :white_rating, :black_rating, :result, :user_color, :pgn,
         COALESCE((SELECT analyzed FROM games WHERE id = :id), 0))""",
        game,
    )


def save_analysis(conn: sqlite3.Connection, game_id: str, result: dict) -> None:
    """Guarda jugadas + resumen de una partida y la marca como analizada."""
    conn.execute("DELETE FROM moves WHERE game_id = ?", (game_id,))
    for move in result["moves"]:
        conn.execute(
            """INSERT OR REPLACE INTO moves
            (game_id, ply, move_number, color, san, uci, fen_before, fen_after, eval_cp,
             best_uci, best_san, cp_loss, winprob_drop, classification, is_user_move)
            VALUES
            (:game_id, :ply, :move_number, :color, :san, :uci, :fen_before, :fen_after, :eval_cp,
             :best_uci, :best_san, :cp_loss, :winprob_drop, :classification, :is_user_move)""",
            {**move, "game_id": game_id},
        )
    conn.execute(
        """INSERT OR REPLACE INTO game_summary
        (game_id, inaccuracies, mistakes, blunders, acpl, accuracy, coach_note)
        VALUES (:game_id, :inaccuracies, :mistakes, :blunders, :acpl, :accuracy,
                COALESCE((SELECT coach_note FROM game_summary WHERE game_id = :game_id), NULL))""",
        {**result["summary"], "game_id": game_id},
    )
    conn.execute("UPDATE games SET analyzed = 1 WHERE id = ?", (game_id,))


def save_coach_note(conn: sqlite3.Connection, game_id: str, note: str) -> None:
    conn.execute(
        "UPDATE game_summary SET coach_note = ? WHERE game_id = ?", (note, game_id)
    )
