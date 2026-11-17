r"""Backend FastAPI: expone partidas, análisis y coach para el frontend.

Arrancar (desde la raíz del proyecto):
    .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

Con --host 0.0.0.0 podrás abrirlo desde el móvil en la misma WiFi:
    http://<IP-de-tu-PC>:8000
"""
from __future__ import annotations

import hashlib
import io
import time

import chess.pgn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db
from .coach import gemini
from .engine import analyzer
from .features import puzzles, stats
from .ingest import chesscom

app = FastAPI(title="chess-master API", version="0.2")

# El frontend (móvil u otro origen) necesita poder llamar a esta API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()


@app.get("/api/health")
def health():
    sf = config.find_stockfish()
    has_gemini = bool((config.GEMINI_API_KEY or "").strip())
    return {
        "ok": True,
        "stockfish": bool(sf),
        "engine": "stockfish" if sf else "heuristic-chess",
        "gemini": has_gemini,
        "coach": "gemini" if has_gemini else "offline-coach",
        "user": config.CHESSCOM_USERNAME,
    }


@app.get("/api/games")
def list_games():
    """Lista de partidas con su resumen de análisis (si lo tienen)."""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT g.id, g.end_time, g.time_class, g.white, g.black,
                      g.white_rating, g.black_rating, g.result, g.user_color,
                      g.eco, g.analyzed,
                      s.inaccuracies, s.mistakes, s.blunders, s.acpl, s.accuracy
               FROM games g LEFT JOIN game_summary s ON s.game_id = g.id
               ORDER BY g.end_time DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/game")
def get_game(id: str = Query(..., description="URL de la partida en Chess.com")):
    """Detalle de una partida: cabecera + jugadas analizadas + resumen + coach."""
    with db.connect() as conn:
        game = conn.execute("SELECT * FROM games WHERE id = ?", (id,)).fetchone()
        if not game:
            raise HTTPException(404, "Partida no encontrada")
        moves = conn.execute(
            "SELECT * FROM moves WHERE game_id = ? ORDER BY ply", (id,)
        ).fetchall()
        summary = conn.execute(
            "SELECT * FROM game_summary WHERE game_id = ?", (id,)
        ).fetchone()
    return {
        "game": dict(game),
        "moves": [dict(m) for m in moves],
        "summary": dict(summary) if summary else None,
    }


class FetchReq(BaseModel):
    months: int | None = None
    max: int | None = None
    username: str | None = None


@app.post("/api/fetch")
def fetch(req: FetchReq):
    """Descarga partidas nuevas de Chess.com."""
    user = (req.username or config.CHESSCOM_USERNAME or "").strip()
    if not user:
        raise HTTPException(400, "Indica tu usuario de Chess.com o configúralo en .env")
    config.set_chesscom_username(user)
    n = chesscom.fetch_user_games(user, max_months=req.months, max_games=req.max)
    return {"saved": n, "user": user}


_DEMO_PGN = """[Event "Partida Demo Táctica"]
[Site "ChessMaster Local"]
[Date "2026.05.01"]
[White "TuUsuario"]
[Black "RivalClub"]
[Result "0-1"]
[ECO "C50"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. d3 Nf6 5. Nc3 d6 6. Bg5 h6 7. Bh4 g5 8. Bg3 Bg4
9. h3 Bh5 10. Qe2 Nd4 11. Qd1 Nxf3+ 12. gxf3 Bg6 13. Qd2 Nh5 14. O-O-O Nxg3
15. fxg3 c6 16. Kb1 b5 17. Bb3 a5 18. Qc1 Qb6 0-1
"""


def _store_pgn_game(pgn_text: str, user_color: str = "white", username: str = "Jugador") -> str:
    pgn_clean = (pgn_text or "").strip()
    if not pgn_clean:
        raise HTTPException(400, "El PGN no puede estar vacío.")
    parsed = chess.pgn.read_game(io.StringIO(pgn_clean))
    if parsed is None or not list(parsed.mainline_moves()):
        raise HTTPException(400, "PGN inválido o sin jugadas.")

    color = "black" if str(user_color).lower().startswith("b") else "white"
    headers = parsed.headers
    white_name = headers.get("White") or (username if color == "white" else "Rival")
    black_name = headers.get("Black") or (username if color == "black" else "Rival")
    pgn_res = headers.get("Result", "*")
    if pgn_res == "1-0":
        result = "win" if color == "white" else "lose"
    elif pgn_res == "0-1":
        result = "win" if color == "black" else "lose"
    elif pgn_res == "1/2-1/2":
        result = "draw"
    else:
        result = "draw"

    game_hash = hashlib.sha1(pgn_clean.encode("utf-8")).hexdigest()[:12]
    game_id = f"local:{game_hash}"
    norm = {
        "id": game_id,
        "end_time": int(time.time()),
        "time_class": headers.get("TimeControl") or "rapid",
        "time_control": headers.get("TimeControl") or "600",
        "rated": 0,
        "rules": "chess",
        "eco": headers.get("ECO") or None,
        "eco_url": None,
        "white": white_name,
        "black": black_name,
        "white_rating": int(headers["WhiteElo"]) if headers.get("WhiteElo", "").isdigit() else None,
        "black_rating": int(headers["BlackElo"]) if headers.get("BlackElo", "").isdigit() else None,
        "result": result,
        "user_color": color,
        "pgn": pgn_clean,
    }
    db.init_db()
    with db.connect() as conn:
        db.upsert_game(conn, norm)
        conn.commit()
    return game_id


class ImportPgnReq(BaseModel):
    pgn: str
    user_color: str = "white"
    username: str = "Jugador"


@app.post("/api/games/import-pgn")
def import_pgn(req: ImportPgnReq):
    """Importa una partida en formato PGN directamente desde la web."""
    gid = _store_pgn_game(req.pgn, user_color=req.user_color, username=req.username)
    return {"saved": 1, "id": gid}


@app.post("/api/games/demo")
def create_demo_game():
    """Carga una partida táctica de demostración lista para analizar sin internet."""
    gid = _store_pgn_game(_DEMO_PGN, user_color="white", username="TuUsuario")
    return {"saved": 1, "id": gid}


@app.post("/api/game/analyze")
def analyze_game(id: str = Query(...), depth: int | None = None):
    """Analiza una partida con Stockfish y guarda el resultado."""
    with db.connect() as conn:
        game = conn.execute("SELECT * FROM games WHERE id = ?", (id,)).fetchone()
        if not game:
            raise HTTPException(404, "Partida no encontrada")
        result = analyzer.analyze_pgn(game["pgn"], game["user_color"], depth=depth)
        db.save_analysis(conn, id, result)
        conn.commit()
    return {"summary": result["summary"]}


@app.post("/api/game/coach")
def coach_game(id: str = Query(...)):
    """Genera (y guarda) el comentario del entrenador con Gemini."""
    with db.connect() as conn:
        game = conn.execute("SELECT * FROM games WHERE id = ?", (id,)).fetchone()
        if not game:
            raise HTTPException(404, "Partida no encontrada")
        summary = conn.execute(
            "SELECT * FROM game_summary WHERE game_id = ?", (id,)
        ).fetchone()
        if not summary:
            raise HTTPException(400, "Analiza la partida antes de pedir el comentario.")
        moves = conn.execute(
            "SELECT * FROM moves WHERE game_id = ? ORDER BY ply", (id,)
        ).fetchall()
        analysis = {"moves": [dict(m) for m in moves], "summary": dict(summary)}
        note = gemini.coach_game(dict(game), analysis)
        db.save_coach_note(conn, id, note)
        conn.commit()
    return {"coach_note": note}


@app.post("/api/game/move-coach")
def move_coach(id: str = Query(...), ply: int = Query(...)):
    """Explicación del entrenador para UNA jugada concreta."""
    with db.connect() as conn:
        game = conn.execute("SELECT * FROM games WHERE id = ?", (id,)).fetchone()
        if not game:
            raise HTTPException(404, "Partida no encontrada")
        move = conn.execute(
            "SELECT * FROM moves WHERE game_id = ? AND ply = ?", (id, ply)
        ).fetchone()
        if not move:
            raise HTTPException(404, "Jugada no encontrada (¿está analizada la partida?)")
        text = gemini.coach_move(dict(game), dict(move))
    return {"explanation": text}


@app.get("/api/stats")
def get_stats():
    """Estadísticas agregadas entre partidas (patrones, fases y aperturas)."""
    return stats.compute_stats()


@app.get("/api/puzzles")
def list_puzzles(limit: int = 20):
    """Ejercicios tácticos generados desde tus propios errores."""
    return puzzles.get_puzzles(limit)


# Servir el frontend (PWA). Debe ir al final: las rutas /api/* tienen prioridad.
_frontend = config.ROOT / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
