"""Coach basado en Google Gemini (tier gratuito).

El LLM SOLO redacta a partir de los datos exactos de Stockfish. Nunca calcula
táctica ni inventa jugadas: así las explicaciones son fiables.
"""
from __future__ import annotations

import httpx

from .. import config

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = (
    "Eres un entrenador de ajedrez paciente, claro y motivador. Recibes datos EXACTOS "
    "calculados por el motor Stockfish (evaluaciones, mejor jugada y tipo de error). "
    "Reglas estrictas: (1) NUNCA inventes jugadas ni evaluaciones; usa solo los datos dados. "
    "(2) Responde en español. (3) Sé breve y didáctico. (4) Habla directamente al alumno."
)


def _call(prompt: str, max_tokens: int = 1024) -> str:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Falta GEMINI_API_KEY en el .env")
    url = API_URL.format(model=config.GEMINI_MODEL)
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": max_tokens,
            # Gemini 2.5 Flash razona por defecto y esos tokens "se comen" la salida.
            # No necesitamos razonamiento profundo solo para redactar -> lo desactivamos.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    with httpx.Client(timeout=60.0) as c:
        r = c.post(url, params={"key": config.GEMINI_API_KEY}, json=payload)
        r.raise_for_status()
        data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Respuesta inesperada de Gemini: {data}") from exc


def _key_moments(analysis: dict, max_moments: int = 6) -> list[dict]:
    """Selecciona los peores errores del usuario, de mayor a menor gravedad."""
    errs = [
        m for m in analysis["moves"]
        if m["is_user_move"] and m["classification"] in ("inaccuracy", "mistake", "blunder")
    ]
    errs.sort(key=lambda m: m["winprob_drop"], reverse=True)
    return errs[:max_moments]


def coach_game(game_info: dict, analysis: dict) -> str:
    s = analysis["summary"]
    moments = _key_moments(analysis)
    if moments:
        lines = "\n".join(
            f"- Jugada {m['move_number']} ({m['color']}): jugaste {m['san']} "
            f"[{m['classification']}]; lo mejor era {m['best_san']} "
            f"(evaluación tras tu jugada: {m['eval_cp'] / 100:+.2f})."
            for m in moments
        )
    else:
        lines = "- No cometiste errores graves; partida muy sólida."

    prompt = f"""Partida: {game_info.get('white')} (blancas) vs {game_info.get('black')} (negras).
El alumno jugó con las {('blancas' if game_info.get('user_color') == 'white' else 'negras')} y el resultado para él fue: {game_info.get('result')}.
Apertura (ECO): {game_info.get('eco') or 'desconocida'}.

Datos del motor (Stockfish):
- Imprecisiones: {s['inaccuracies']}, Errores: {s['mistakes']}, Blunders: {s['blunders']}
- Precisión estimada: {s['accuracy']}% (pérdida media: {s['acpl']} centipawns)

Momentos clave (datos exactos, no inventes nada más):
{lines}

Escribe un comentario de entrenador (máximo 200 palabras): empieza con algo positivo,
explica el PATRÓN de los errores (no solo los listes), y termina con 2-3 consejos
concretos y accionables para mejorar."""
    return _call(prompt)
