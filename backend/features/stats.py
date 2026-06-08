"""Estadísticas agregadas entre partidas: patrones, fases y aperturas."""
from __future__ import annotations

from .. import db


def _piece_count(fen: str) -> int:
    return sum(1 for ch in fen.split(" ")[0] if ch.isalpha())


def _phase(ply: int, classification: str, fen_before: str) -> str:
    """Clasifica la jugada en apertura / medio juego / final."""
    if classification == "book" or ply <= 16:
        return "opening"
    if _piece_count(fen_before) <= 12:
        return "endgame"
    return "middlegame"


def _opening_name(game: dict) -> str:
    url = game.get("eco_url")
    if url:
        seg = url.rstrip("/").split("/")[-1]
        if seg:
            return seg.replace("-", " ")
    return game.get("eco") or "Desconocida"


def _tally(games: list[dict]) -> dict:
    accs = [g["accuracy"] for g in games if g.get("accuracy") is not None]
    return {
        "games": len(games),
        "wins": sum(1 for g in games if g["result"] == "win"),
        "losses": sum(1 for g in games if g["result"] == "lose"),
        "draws": sum(1 for g in games if g["result"] == "draw"),
        "accuracy": round(sum(accs) / len(accs), 1) if accs else None,
    }


def compute_stats() -> dict:
    with db.connect() as conn:
        games = [dict(r) for r in conn.execute(
            """SELECT g.*, s.accuracy, s.acpl
               FROM games g LEFT JOIN game_summary s ON s.game_id = g.id"""
        ).fetchall()]
        moves = [dict(r) for r in conn.execute(
            "SELECT ply, classification, fen_before, cp_loss FROM moves WHERE is_user_move = 1"
        ).fetchall()]

    analyzed = [g for g in games if g.get("accuracy") is not None]
    totals = _tally(games)
    totals["analyzed"] = len(analyzed)
    totals["avg_acpl"] = round(sum(g["acpl"] for g in analyzed) / len(analyzed), 1) if analyzed else None

    by_color = {
        "white": _tally([g for g in games if g["user_color"] == "white"]),
        "black": _tally([g for g in games if g["user_color"] == "black"]),
    }

    classifications: dict[str, int] = {}
    for m in moves:
        classifications[m["classification"]] = classifications.get(m["classification"], 0) + 1

    phases = {ph: {"moves": 0, "cp_loss": 0, "inaccuracies": 0, "mistakes": 0, "blunders": 0}
              for ph in ("opening", "middlegame", "endgame")}
    for m in moves:
        d = phases[_phase(m["ply"], m["classification"], m["fen_before"] or "")]
        d["moves"] += 1
        d["cp_loss"] += min(m["cp_loss"] or 0, 1000)
        if m["classification"] == "blunder":
            d["blunders"] += 1
        elif m["classification"] in ("mistake", "miss"):
            d["mistakes"] += 1
        elif m["classification"] == "inaccuracy":
            d["inaccuracies"] += 1
    for d in phases.values():
        d["acpl"] = round(d["cp_loss"] / d["moves"], 1) if d["moves"] else 0.0
        del d["cp_loss"]

    op: dict[str, dict] = {}
    for g in games:
        name = _opening_name(g)
        o = op.setdefault(name, {"opening": name, "games": 0, "wins": 0,
                                 "losses": 0, "draws": 0, "_acc": []})
        o["games"] += 1
        if g["result"] == "win":
            o["wins"] += 1
        elif g["result"] == "lose":
            o["losses"] += 1
        else:
            o["draws"] += 1
        if g.get("accuracy") is not None:
            o["_acc"].append(g["accuracy"])
    openings = []
    for o in op.values():
        o["accuracy"] = round(sum(o["_acc"]) / len(o["_acc"]), 1) if o["_acc"] else None
        del o["_acc"]
        openings.append(o)
    openings.sort(key=lambda x: x["games"], reverse=True)

    by_time: dict[str, list] = {}
    for g in games:
        by_time.setdefault(g.get("time_class") or "otro", []).append(g)
    by_time = {k: _tally(v) for k, v in by_time.items()}

    def _game_info(g: dict) -> dict:
        opp = g["black"] if g["user_color"] == "white" else g["white"]
        return {"opponent": opp, "accuracy": g["accuracy"], "result": g["result"]}

    ranked = sorted(analyzed, key=lambda g: g["accuracy"])
    best_game = _game_info(ranked[-1]) if ranked else None
    worst_game = _game_info(ranked[0]) if ranked else None

    return {
        "totals": totals,
        "by_color": by_color,
        "by_time": by_time,
        "best_game": best_game,
        "worst_game": worst_game,
        "classifications": classifications,
        "phases": phases,
        "openings": openings[:12],
    }
