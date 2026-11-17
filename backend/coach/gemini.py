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


def _offline_coach_game(game_info: dict, analysis: dict) -> str:
    """Genera un informe estructurado de entrenador sin depender de una API externa."""
    s = analysis["summary"]
    moments = _key_moments(analysis, max_moments=4)
    color_txt = "blancas" if game_info.get("user_color") == "white" else "negras"
    acc = s.get("accuracy", 0)
    acpl = s.get("acpl", 0)
    blunders = s.get("blunders", 0)
    mistakes = s.get("mistakes", 0)
    inaccuracies = s.get("inaccuracies", 0)

    if acc >= 85:
        intro = f"**Buen trabajo con las {color_txt}** ({acc}% de precisión estimada, ACPL {acpl}). Mantuviste un juego sólido en casi toda la partida."
    elif acc >= 70:
        intro = f"**Partida competitiva con las {color_txt}** ({acc}% de precisión estimada, ACPL {acpl}). Hay una base buena con algunos momentos críticos por pulir."
    else:
        intro = f"**Partida exigente con las {color_txt}** ({acc}% de precisión estimada, ACPL {acpl}). Perfecta para detectar patrones tácticos concretos."

    parts = [intro]
    parts.append(
        f"**Resumen de errores:** {blunders} blunder(s), {mistakes} error(es) y {inaccuracies} imprecisión(es)."
    )

    if moments:
        parts.append("**Momentos clave a revisar:**")
        for m in moments:
            best = m.get("best_san") or "otra continuación"
            ev = (m.get("eval_cp") or 0) / 100.0
            parts.append(
                f"- Jugada {m['move_number']}: elegiste **{m['san']}** ({m['classification']}); "
                f"era más precisa **{best}** (eval {ev:+.2f})."
            )
    else:
        parts.append("- No dejaste escapar errores graves en tus jugadas principales.")

    tips = ["**Consejos prácticos:**"]
    if blunders > 0:
        tips.append("- Antes de confirmar la jugada, comprueba capturas, jaques y piezas sin defensa (check blunders).")
    if mistakes > 0 or inaccuracies > 0:
        tips.append("- En posiciones tensas, compara al menos 2 jugadas candidatas buscando mejorar tu peor pieza.")
    tips.append("- Usa la pestaña **🎯 Entrenar** para repetir exactamente estas posiciones críticas desde el tablero.")
    parts.extend(tips)
    return "\n".join(parts)


def _offline_coach_move(game_info: dict, move: dict) -> str:
    """Explicación local didáctica para una jugada concreta cuando no hay Gemini."""
    cls = move.get("classification", "good")
    san = move.get("san", "")
    best = move.get("best_san")
    ev = (move.get("eval_cp") or 0) / 100.0
    cp_loss = (move.get("cp_loss") or 0) / 100.0
    is_mine = move.get("color") == game_info.get("user_color")
    quien = "Tu jugada" if is_mine else "La jugada de tu rival"

    if cls in ("best", "brilliant", "great", "excellent", "good", "book"):
        txt = f"{quien} **{san}** está bien valorada (**{cls}**, evaluación {ev:+.2f})."
        if best and best != san:
            txt += f" Una alternativa principal era **{best}**."
        return txt

    txt = f"{quien} **{san}** se clasifica como **{cls}** (pérdida de ~{cp_loss:.2f} peones, evaluación {ev:+.2f})."
    if best and best != san:
        txt += f" La opción recomendada por el motor era **{best}** para mantener mejor coordinación y seguridad."
    return txt


def coach_game(game_info: dict, analysis: dict) -> str:
    s = analysis["summary"]
    moments = _key_moments(analysis)
    if not (config.GEMINI_API_KEY or "").strip():
        return _offline_coach_game(game_info, analysis)

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
    try:
        return _call(prompt)
    except Exception:
        return _offline_coach_game(game_info, analysis)


def coach_move(game_info: dict, move: dict) -> str:
    """Explicación breve y enfocada de UNA jugada concreta."""
    if not (config.GEMINI_API_KEY or "").strip():
        return _offline_coach_move(game_info, move)

    color = "blancas" if move["color"] == "white" else "negras"
    autor = "tuya (del alumno)" if move["color"] == game_info.get("user_color") else "de tu rival"
    lines = [
        f"Partida {game_info.get('white')} vs {game_info.get('black')}. "
        f"Analiza la jugada {move['move_number']} de las {color}, que es {autor}.",
        f"- Jugada realizada: {move['san']} (el motor la clasifica como '{move['classification']}').",
        f"- Evaluación tras la jugada: {move['eval_cp'] / 100:+.2f} (perspectiva de las blancas).",
    ]
    if move.get("best_san") and move["best_san"] != move["san"]:
        lines.append(f"- La mejor jugada según Stockfish era: {move['best_san']}.")
    lines.append(
        "Explica en español (máx. 80 palabras): por qué merece esa etiqueta, la idea "
        "detrás y, si aplica, qué era mejor y por qué. Si la jugada es de tu rival, "
        "refiérete a ella como la de tu oponente, no como tuya."
    )
    try:
        return _call("\n".join(lines), max_tokens=400)
    except Exception:
        return _offline_coach_move(game_info, move)
