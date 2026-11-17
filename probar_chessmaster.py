#!/usr/bin/env python3
"""Suite de pruebas automatizadas de chess-master (motor heurístico, coach offline, API y puzzles)."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

TMP_DIR = Path(tempfile.mkdtemp(prefix="chessmaster_test_"))
os.environ["CHESSMASTER_DB_PATH"] = str(TMP_DIR / "test_chess.db")
os.environ.pop("GEMINI_API_KEY", None)
os.environ["STOCKFISH_PATH"] = ""

from fastapi.testclient import TestClient  # noqa: E402
from backend import config, db  # noqa: E402
from backend.engine import analyzer  # noqa: E402
from backend.main import app  # noqa: E402

fallos: list[str] = []


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    if condicion:
        print(f"  [OK]    {nombre}")
    else:
        print(f"  [FALLO] {nombre}" + (f" — {detalle}" if detalle else ""))
        fallos.append(nombre)


BLUNDER_PGN = """[Event "Test Táctico"]
[White "Alumno"]
[Black "Rival"]
[Result "0-1"]
[ECO "C20"]

1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0
"""

SCHOLAR_LOSE_PGN = """[Event "Test Blunder"]
[White "Alumno"]
[Black "Rival"]
[Result "0-1"]
[ECO "C20"]

1. f3 e5 2. g4 Qh4# 0-1
"""


def caso_motor_heuristico() -> None:
    print("\n1. Motor heurístico local y clasificación")
    orig_find = config.find_stockfish
    config.find_stockfish = lambda: None
    try:
        res = analyzer.analyze_pgn(SCHOLAR_LOSE_PGN, user_color="white")
        comprobar("analyze_pgn funciona sin binario Stockfish", len(res["moves"]) == 4)
        s = res["summary"]
        comprobar(
            "detecta error/blunder cuando las blancas permiten mate rápido",
            (s["blunders"] + s["mistakes"]) >= 1,
            str(s),
        )
    finally:
        config.find_stockfish = orig_find


def caso_api_y_puzzles() -> None:
    print("\n2. API FastAPI, PGN, coach offline y puzzles")
    db.init_db()
    with TestClient(app) as client:
        r_health = client.get("/api/health")
        comprobar(
            "GET /api/health responde ok con modo coach",
            r_health.status_code == 200 and r_health.json().get("ok") is True and "coach" in r_health.json(),
            r_health.text,
        )

        r_bad_fetch = client.post("/api/fetch", json={"username": ""})
        comprobar("POST /api/fetch sin usuario devuelve HTTP 400", r_bad_fetch.status_code == 400)

        r_bad_pgn = client.post("/api/games/import-pgn", json={"pgn": "esto no es un pgn valido"})
        comprobar("POST /api/games/import-pgn inválido devuelve HTTP 400", r_bad_pgn.status_code == 400)

        r_imp = client.post("/api/games/import-pgn", json={
            "pgn": SCHOLAR_LOSE_PGN,
            "user_color": "white",
            "username": "Alumno",
        })
        comprobar("POST /api/games/import-pgn guarda partida", r_imp.status_code == 200 and r_imp.json().get("id"))
        gid = r_imp.json()["id"]

        r_demo = client.post("/api/games/demo")
        comprobar("POST /api/games/demo carga partida demo", r_demo.status_code == 200 and r_demo.json().get("saved") == 1)

        r_an = client.post(f"/api/game/analyze?id={gid}")
        comprobar("POST /api/game/analyze analiza con respaldo heurístico", r_an.status_code == 200 and "summary" in r_an.json())

        r_coach = client.post(f"/api/game/coach?id={gid}")
        comprobar(
            "POST /api/game/coach responde en modo offline",
            r_coach.status_code == 200 and len(r_coach.json().get("coach_note", "")) > 20,
            r_coach.text,
        )

        r_mcoach = client.post(f"/api/game/move-coach?id={gid}&ply=2")
        comprobar(
            "POST /api/game/move-coach responde por jugada",
            r_mcoach.status_code == 200 and len(r_mcoach.json().get("explanation", "")) > 10,
        )

        r_stats = client.get("/api/stats")
        comprobar("GET /api/stats devuelve estadísticas", r_stats.status_code == 200 and r_stats.json()["totals"]["games"] >= 2)

        demo_id = r_demo.json()["id"]
        client.post(f"/api/game/analyze?id={demo_id}")
        r_puz = client.get("/api/puzzles")
        comprobar("GET /api/puzzles genera ejercicios tácticos", r_puz.status_code == 200 and len(r_puz.json()) >= 1, r_puz.text)

        r_ui = client.get("/")
        comprobar("GET / sirve el frontend PWA", r_ui.status_code == 200 and "Chess Master" in r_ui.text)


def main() -> int:
    try:
        caso_motor_heuristico()
        caso_api_y_puzzles()
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    print()
    if fallos:
        print(f"RESULTADO: {len(fallos)} comprobación(es) fallida(s):")
        for f in fallos:
            print(f"  · {f}")
        return 1
    print("RESULTADO: todas las comprobaciones pasan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
