# ♟️ chess-master

Analiza tus partidas de **Chess.com** combinando **Stockfish** (análisis táctico
fiable) con un entrenador en lenguaje natural (**Gemini**, tier gratuito).

Diseño completo en [DESIGN.md](DESIGN.md).

## Requisitos

- Python 3.11+ (probado con 3.14)
- Stockfish (se descarga en `stockfish/`)
- Una clave gratuita de Gemini → https://aistudio.google.com

## Instalación

```powershell
# 1. Crear entorno virtual e instalar dependencias
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Configurar credenciales
copy .env.example .env   # y edita .env con tu clave y tu usuario
```

## Uso

```powershell
# Descargar tus partidas (p. ej. los últimos 3 meses)
.\.venv\Scripts\python.exe -m scripts.fetch_games --months 3

# Analizar con Stockfish
.\.venv\Scripts\python.exe -m scripts.analyze --limit 1 --depth 14

# Generar el comentario del entrenador (Gemini)
.\.venv\Scripts\python.exe -m scripts.coach
```

## Seguridad

La clave de la API se guarda en `.env`, que está en `.gitignore` y **nunca** se
sube a git. Si crees que se ha filtrado, regenérala en https://aistudio.google.com.

## Créditos

- Piezas de ajedrez: set **cburnett** (Colin M.L. Burnett), de [Lichess](https://github.com/lichess-org/lila), bajo licencia GPLv2+.
- Motor: [Stockfish](https://stockfishchess.org/) (GPLv3).
