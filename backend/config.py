"""Configuración central: carga .env, rutas y ajustes del análisis."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- Credenciales / cuentas ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CHESSCOM_USERNAME = os.getenv("CHESSCOM_USERNAME", "")

# --- Rutas ---
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "chess.db"
STOCKFISH_DIR = ROOT / "stockfish"


def find_stockfish() -> str | None:
    """Localiza el ejecutable de Stockfish (variable de entorno o carpeta stockfish/)."""
    env_path = os.getenv("STOCKFISH_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    if STOCKFISH_DIR.exists():
        # En Windows el binario se llama stockfish*.exe; en Linux/Mac sin extensión.
        for pattern in ("stockfish*.exe", "stockfish*"):
            exes = [p for p in STOCKFISH_DIR.rglob(pattern) if p.is_file()]
            if exes:
                return str(exes[0])
    return None


STOCKFISH_PATH = find_stockfish()

# --- Ajustes del análisis ---
ANALYSIS_DEPTH = int(os.getenv("ANALYSIS_DEPTH", "18"))

# Umbrales de clasificación por caída de probabilidad de victoria (0..1).
# Ajustados para parecerse al informe de Chess.com (se pueden tunear).
WINPROB_GOOD = 0.02
WINPROB_INACCURACY = 0.05
WINPROB_MISTAKE = 0.10
WINPROB_BLUNDER = 0.20

# Chess.com exige un User-Agent identificativo o devuelve 403.
HTTP_USER_AGENT = f"chess-master/0.1 (analysis tool; user: {CHESSCOM_USERNAME or 'unknown'})"
