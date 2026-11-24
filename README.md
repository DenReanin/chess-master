# ♟️ Chess Master

Analizador táctico interactivo de partidas de ajedrez (Chess.com y PGN) que combina **Stockfish** (con respaldo heurístico local integrado si no hay binario instalado), entrenador en lenguaje natural (**Gemini** o modo **offline** integrado), gráficas de evaluación y ejercicios tácticos generados a partir de tus propios errores.

Diseño y arquitectura en [DESIGN.md](DESIGN.md).

---

## Características principales

- **Importación automática desde Chess.com y PGN manual**: descarga tus partidas recientes o pega directamente cualquier PGN desde la interfaz o la CLI.
- **Análisis táctico híbrido**: evalúa jugada por jugada con **Stockfish** (UCI) e incluye un **motor heurístico local** de respaldo para funcionar sin dependencias externas.
- **Entrenador IA / Offline**: explica por qué una jugada fue imprecisión, error grave o blunder con Gemini (`gemini-2.5-flash`) o mediante el analizador táctico local sin API.
- **Entrenamiento interactivo**: genera puzzles tácticos desde tus propios errores, tablero SVG interactivo (`cburnett`) y estadísticas de aperturas y fases.
- **PWA multiplataforma**: funciona en **Linux** (`./run-chess-master.sh`) y **Windows**, con acceso cómodo desde el navegador del PC o móvil en red local.

---

## Instalación rápida

### Linux (`run-chess-master.sh`)
```bash
git clone https://github.com/DenReanin/chess-master.git
cd chess-master
./run-chess-master.sh
```
*(También puedes configurarlo paso a paso: `python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt && cp .env.example .env`).*

### Windows (PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Variables opcionales (`.env`)
- `GEMINI_API_KEY`: clave opcional de [Google AI Studio](https://aistudio.google.com) para el entrenador en lenguaje natural (sin clave usa el coach offline integrado).
- `STOCKFISH_PATH`: ruta al ejecutable de Stockfish (si no está instalado, usa evaluación heurística local).
- `CHESSCOM_USERNAME`: usuario por defecto al importar partidas.

---

## Pruebas automatizadas

```bash
./.venv/bin/python probar_chessmaster.py
```

---

## Seguridad y privacidad

- Las credenciales se leen únicamente desde `.env` (excluido por `.gitignore`).
- Si usas el modo offline (sin `GEMINI_API_KEY`), todo el análisis y entrenamiento se ejecutan localmente en tu máquina.

## Créditos y licencia

- Código del proyecto bajo licencia [MIT](LICENSE).
- Piezas de ajedrez: set **cburnett** (Colin M.L. Burnett), de [Lichess](https://github.com/lichess-org/lila), bajo licencia GPLv2+.
- Motor compatible: [Stockfish](https://stockfishchess.org/) (GPLv3).
