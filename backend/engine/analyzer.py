"""Análisis de partidas con Stockfish, con clasificación de jugadas estilo Chess.com.

Categorías: brilliant, great, best, excellent, good, book, inaccuracy, miss, mistake, blunder.

El motor (Stockfish) es la fuente de la verdad para las evaluaciones. Las etiquetas
de brilliant/great/miss/book son heurísticas razonables (el algoritmo exacto de
Chess.com es propietario), construidas sobre esas evaluaciones exactas.
"""
from __future__ import annotations

import io
import math

import chess
import chess.engine
import chess.pgn

from .. import config
from . import openings

WINPROB_K = 0.00368208   # modelo logístico de probabilidad de victoria (Lichess)
CAP = 2000               # tope de centipawns (evita overflow y el dominio de los mates)
BOOK_PLIES = 16          # hasta ~8 jugadas por bando cuentan como "teoría" si son buenas
GREAT_GAP = 180          # cp: si la mejor supera a la 2ª por este margen, la posición es crítica
SAC_MATERIAL = 1.5       # peones: material mínimo sacrificado para considerar "brillante"

PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9,
}


def _cap(cp: int) -> int:
    return max(-CAP, min(CAP, cp))


def winprob(cp: float) -> float:
    """Probabilidad de victoria (0..1) desde la perspectiva del que mueve."""
    return 1.0 / (1.0 + math.exp(-WINPROB_K * _cap(cp)))


def _move_accuracy(wp_before: float, wp_after: float) -> float:
    drop = max(0.0, wp_before - wp_after) * 100.0
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * drop) - 3.1669))


def _terminal_eval(board: chess.Board) -> int:
    if board.is_checkmate():
        return -CAP if board.turn == chess.WHITE else CAP
    return 0


def _material(board: chess.Board) -> int:
    """Material neto desde la perspectiva de las blancas (en peones)."""
    total = 0
    for pt, val in PIECE_VALUES.items():
        total += val * (len(board.pieces(pt, chess.WHITE)) - len(board.pieces(pt, chess.BLACK)))
    return total


def _analyse_positions(engine, fens, depth):
    """Devuelve, por posición: eval de la mejor, eval de la 2ª mejor, y la mejor jugada."""
    limit = chess.engine.Limit(depth=depth)
    top1, top2, best = [], [], []
    for fen in fens:
        bd = chess.Board(fen)
        if bd.is_game_over():
            ev = _terminal_eval(bd)
            top1.append(ev); top2.append(ev); best.append(None)
            continue
        infos = engine.analyse(bd, limit, multipv=2)
        s1 = infos[0]["score"].white().score(mate_score=100000)
        pv1 = infos[0].get("pv")
        top1.append(s1)
        best.append(pv1[0] if pv1 else None)
        if len(infos) > 1:
            top2.append(infos[1]["score"].white().score(mate_score=100000))
        else:
            top2.append(s1)
    return top1, top2, best


def _classify(i, mover_white, top1, top2, best_moves, moves, board):
    """Clasifica la jugada i en una de las 10 categorías estilo Chess.com."""
    sign = 1 if mover_white else -1
    cp_best = sign * top1[i]            # eval jugando la MEJOR jugada
    cp_played = sign * top1[i + 1]      # eval tras la jugada REAL
    cp_second = sign * top2[i]          # eval de la 2ª mejor jugada
    wp_before, wp_after = winprob(cp_best), winprob(cp_played)
    wp_drop = max(0.0, wp_before - wp_after)
    is_best = best_moves[i] is not None and moves[i] == best_moves[i]
    gap = cp_best - cp_second           # cuánto supera la mejor a la segunda (>=0)

    # Categoría base por pérdida de probabilidad de victoria (umbrales configurables).
    if wp_drop >= config.WINPROB_BLUNDER:
        base = "blunder"
    elif wp_drop >= config.WINPROB_MISTAKE:
        base = "mistake"
    elif wp_drop >= config.WINPROB_INACCURACY:
        base = "inaccuracy"
    elif wp_drop >= config.WINPROB_GOOD:
        base = "good"
    elif not is_best:
        base = "excellent"
    else:
        base = "best"

    cp_loss = max(0, _cap(cp_best) - _cap(cp_played))

    if base in ("inaccuracy", "mistake", "blunder"):
        # ¿Oportunidad perdida? Tenías ventaja ganadora y la dejaste escapar.
        cls = "miss" if (wp_before >= 0.75 and wp_after <= 0.60) else base
        return cls, wp_before, wp_after, cp_loss

    # Jugadas buenas (best / excellent / good): ¿brillante, gran jugada o teoría?
    sacrifice = False
    if is_best:
        net_before = _material(board)
        tmp = board.copy()
        tmp.push(moves[i])
        opp_best = best_moves[i + 1]
        if opp_best is not None and opp_best in tmp.legal_moves:
            tmp.push(opp_best)
        mover_delta = (_material(tmp) - net_before) * sign  # negativo = sacrificaste
        sacrifice = mover_delta <= -SAC_MATERIAL

    if is_best and sacrifice and 0.50 <= wp_after and wp_before <= 0.97:
        cls = "brilliant"
    elif is_best and gap >= GREAT_GAP and wp_after >= 0.45:
        cls = "great"
    else:
        cls = base
    return cls, wp_before, wp_after, cp_loss


def _is_book(i: int, epd: str, wp_drop: float) -> bool:
    """¿Es teoría de apertura? Usa la base de Lichess; si no, heurística de respaldo."""
    if openings.available():
        return openings.is_book_position(epd)
    return i < BOOK_PLIES and wp_drop < 0.04


def analyze_pgn(pgn_text: str, user_color: str | None, depth: int | None = None) -> dict:
    depth = depth or config.ANALYSIS_DEPTH
    if not config.STOCKFISH_PATH:
        raise RuntimeError(
            "No se encontró Stockfish. Descárgalo en la carpeta stockfish/ "
            "o define STOCKFISH_PATH en el .env."
        )

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("PGN inválido o vacío.")
    moves = list(game.mainline_moves())

    board = game.board()
    fens = [board.fen()]
    for mv in moves:
        board.push(mv)
        fens.append(board.fen())

    engine = chess.engine.SimpleEngine.popen_uci(config.STOCKFISH_PATH)
    try:
        try:
            engine.configure({"Threads": 2, "Hash": 256})
        except Exception:
            pass
        top1, top2, best_moves = _analyse_positions(engine, fens, depth)
    finally:
        engine.quit()

    results = []
    board = game.board()
    for i, mv in enumerate(moves):
        mover_white = board.turn == chess.WHITE
        cls, wp_before, wp_after, cp_loss = _classify(
            i, mover_white, top1, top2, best_moves, moves, board
        )
        if cls in ("best", "excellent", "good"):
            epd = " ".join(fens[i + 1].split()[:4])
            if _is_book(i, epd, wp_before - wp_after):
                cls = "book"
        best_mv = best_moves[i]
        color = "white" if mover_white else "black"
        results.append({
            "ply": i + 1,
            "move_number": board.fullmove_number,
            "color": color,
            "san": board.san(mv),
            "uci": mv.uci(),
            "fen_before": board.fen(),
            "fen_after": fens[i + 1],
            "eval_cp": int(_cap(top1[i + 1])),
            "best_uci": best_mv.uci() if best_mv else None,
            "best_san": board.san(best_mv) if best_mv else None,
            "cp_loss": int(cp_loss),
            "winprob_drop": round(max(0.0, wp_before - wp_after), 4),
            "classification": cls,
            "is_user_move": 1 if (user_color and color == user_color) else 0,
            "_acc": _move_accuracy(wp_before, wp_after),
        })
        board.push(mv)

    user_moves = [m for m in results if m["is_user_move"]]
    n = len(user_moves)

    def count(*names):
        return sum(1 for m in user_moves if m["classification"] in names)

    summary = {
        "inaccuracies": count("inaccuracy"),
        "mistakes": count("mistake", "miss"),
        "blunders": count("blunder"),
        "acpl": round(sum(min(m["cp_loss"], 1000) for m in user_moves) / n, 1) if n else 0.0,
        "accuracy": round(sum(m["_acc"] for m in user_moves) / n, 1) if n else 0.0,
    }
    for m in results:
        m.pop("_acc", None)

    return {"moves": results, "summary": summary}
