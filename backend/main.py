r"""Backend FastAPI: expone partidas, análisis y coach para el frontend.

Arrancar (desde la raíz del proyecto):
    .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

Con --host 0.0.0.0 podrás abrirlo desde el móvil en la misma WiFi:
    http://<IP-de-tu-PC>:8000
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db
from .coach import gemini
from .engine import analyzer
from .ingest import chesscom

app = FastAPI(title="chess-master API", version="0.1")

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
    return {
        "ok": True,
        "stockfish": bool(config.STOCKFISH_PATH),
        "gemini": bool(config.GEMINI_API_KEY),
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


@app.post("/api/fetch")
def fetch(req: FetchReq):
    """Descarga partidas nuevas de Chess.com."""
    n = chesscom.fetch_user_games(
        config.CHESSCOM_USERNAME, max_months=req.months, max_games=req.max
    )
    return {"saved": n}


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


# Servir el frontend (PWA). Debe ir al final: las rutas /api/* tienen prioridad.
_frontend = config.ROOT / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
