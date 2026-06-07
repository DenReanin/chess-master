# chess-master — Diseño

Herramienta personal para analizar mis partidas de **Chess.com** y mejorar mi
ajedrez, combinando un motor real (**Stockfish**) con un "entrenador" en lenguaje
natural (**LLM en la nube, tier gratuito**).

## Principio rector

> El análisis lo hace **Stockfish** (es la fuente de la corrección). El LLM **solo
> redacta** a partir de los datos exactos del motor; nunca calcula táctica ni
> inventa jugadas. Así la herramienta es fiable.

## Arquitectura

```
   📱 Móvil / 💻 PC (navegador, PWA)
            │  WiFi / internet
            ▼
   ┌────────────────────────────────────┐
   │  Backend FastAPI                    │
   │   ├─ Stockfish ........... táctica  │  (local, gratis, fiable)
   │   ├─ Coach (conectable) ──┐         │
   │   ├─ Chess.com API        │         │
   │   └─ SQLite (caché)       │         │
   └───────────────────────────┼─────────┘
                               ▼
                    ☁️ Gemini 2.5 Flash (free)   ← solo redacta
```

- **Backend**: Python + FastAPI. Arranca en el PC; se puede desplegar luego en un
  hosting gratis para usarlo desde cualquier sitio (no depende de GPU).
- **Frontend**: PWA responsive (instalable en el móvil) — fase posterior.
- **Seguridad**: la clave de la API vive **solo en el backend** (`.env`, fuera de git).

## Decisiones cerradas

| Tema | Decisión |
|---|---|
| Fuente de partidas | Chess.com (API pública, sin clave) |
| Motor | Stockfish 18 (build x86-64-avx2) |
| Coach (LLM) | Gemini 2.5 Flash (tier gratuito); **conectable** (Groq/local/plantillas) |
| Modelo local | Descartado (no se usa LM Studio ni la GPU) |
| BBDD | SQLite (un solo usuario) |
| Plataforma | Web responsive / PWA, usable en móvil |

## Clasificación de errores

Para cada jugada se compara la evaluación de **la mejor jugada** con la de **la
jugada real**, medida como caída de **probabilidad de victoria** (modelo logístico
estilo Lichess). Umbrales:

| Caída de prob. victoria | Etiqueta |
|---|---|
| ≥ 0.30 | blunder |
| ≥ 0.20 | mistake (error) |
| ≥ 0.10 | inaccuracy (imprecisión) |
| < 0.10 | good / best |

> El LLM solo comenta los **momentos clave** (los peores errores), no cada jugada:
> así el consumo es mínimo y nunca se acerca al límite gratuito.

## Funciones (hoja de ruta)

1. ✅ **Errores + coaching por partida** — núcleo (Stockfish + Gemini).
2. ⬜ **Patrones en muchas partidas** — estadísticas agregadas (fase en que fallas, etc.).
3. ⬜ **Repertorio de aperturas** — análisis por código ECO.
4. ⬜ **Entrenamiento táctico** — ejercicios a partir de tus propios blunders.

## Fases de construcción

- **Fase 0** — Entorno: Python, Stockfish, clave de Gemini. ✅
- **Fase 1** — Ingesta: descargar partidas de Chess.com → SQLite. ✅
- **Fase 2** — Motor: análisis con Stockfish (blunders, eval, mejor jugada). ✅
- **Fase 3** — Coach: explicaciones con Gemini. ✅
- **Fase 4** — Frontend PWA (tablero + explicaciones, uso en móvil). ⬜
- **Fase 5** — Funciones agregadas (patrones, aperturas, táctica). ⬜

## Estructura

```
chess-master/
├─ backend/
│  ├─ config.py            # .env, rutas, ajustes
│  ├─ db.py                # SQLite (games, moves, game_summary)
│  ├─ ingest/chesscom.py   # descarga de Chess.com
│  ├─ engine/analyzer.py   # análisis con Stockfish
│  └─ coach/
│     ├─ base.py           # interfaz del coach (intercambiable)
│     └─ gemini.py         # implementación con Gemini
├─ scripts/                # CLIs: fetch_games, analyze, coach
├─ stockfish/              # binario (gitignored)
├─ data/                   # chess.db (gitignored)
└─ frontend/               # PWA (fase 4)
```

## Comandos

```bash
# 1. Descargar partidas
py -m scripts.fetch_games --months 3

# 2. Analizar con Stockfish
py -m scripts.analyze --limit 1 --depth 14

# 3. Comentario del entrenador
py -m scripts.coach
```
