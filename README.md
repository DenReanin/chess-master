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

## Arrancar la herramienta (app web)

Levanta el servidor (backend + interfaz) en el puerto **8000**:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Luego ábrela en el navegador:

| Dónde | Dirección |
|---|---|
| 💻 En este PC | `http://127.0.0.1:8000` |
| 📱 En el móvil (misma red WiFi) | `http://<IP-DE-TU-PC>:8000` |

Para saber la IP de tu PC ejecuta `ipconfig` y mira la **IPv4** de tu red local
(algo como `192.168.x.x`). Si el móvil no conecta, permite el puerto **8000** en el
**Firewall de Windows** (la primera vez Windows suele preguntar → "Permitir").

> Es una **PWA**: en el móvil puedes instalarla con el menú del navegador → *"Añadir a pantalla de inicio"*.

### Cómo se usa

1. **Descargar** → trae tus últimas partidas de Chess.com.
2. **Abrir una partida** → se analiza sola con Stockfish y aparece el comentario del entrenador.
3. **📊 Estadísticas** → patrones, fases y aperturas.
4. **🎯 Entrenar** → ejercicios tácticos creados a partir de tus propios errores.

### Avanzado: línea de comandos (opcional)

```powershell
.\.venv\Scripts\python.exe -m scripts.fetch_games --months 3   # descargar partidas
.\.venv\Scripts\python.exe -m scripts.analyze --limit 1        # analizar con Stockfish
.\.venv\Scripts\python.exe -m scripts.coach                    # comentario del entrenador
```

## Seguridad

La clave de la API se guarda en `.env`, que está en `.gitignore` y **nunca** se
sube a git. Si crees que se ha filtrado, regenérala en https://aistudio.google.com.

## Créditos

- Piezas de ajedrez: set **cburnett** (Colin M.L. Burnett), de [Lichess](https://github.com/lichess-org/lila), bajo licencia GPLv2+.
- Motor: [Stockfish](https://stockfishchess.org/) (GPLv3).
