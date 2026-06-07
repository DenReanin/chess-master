"""Interfaz del 'coach' — la capa de explicaciones es intercambiable.

Hoy usamos Gemini (nube, tier gratuito). Mañana se podría enchufar Groq, un
modelo local, o plantillas sin IA, sin tocar el resto del sistema.
"""
from __future__ import annotations

from typing import Protocol


class Coach(Protocol):
    def coach_game(self, game_info: dict, analysis: dict) -> str:
        """Devuelve un comentario de entrenador para una partida completa."""
        ...
