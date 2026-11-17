"use strict";

const $ = (s) => document.querySelector(s);
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

const PIECE_BASE = "/pieces/cburnett/";
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const ARROW_COLOR = "rgba(20, 160, 80, .9)";   // verde: lo que debiste jugar
const BEST_COLOR = "rgba(70, 130, 220, .92)";  // azul: mejor jugada en la posición actual

// Clasificaciones estilo Chess.com: etiqueta, símbolo y color.
const CLS = {
  brilliant:  { label: "Brillante",            sym: "!!", color: "#26c2a3" },
  great:      { label: "Gran jugada",          sym: "!",  color: "#749bbf" },
  best:       { label: "Mejor jugada",         sym: "★",  color: "#81b64c" },
  excellent:  { label: "Excelente",            sym: "✓",  color: "#81b64c" },
  good:       { label: "Buena",                sym: "✓",  color: "#95b776" },
  book:       { label: "Teoría",               sym: "📖", color: "#a88865" },
  inaccuracy: { label: "Imprecisión",          sym: "?!", color: "#f0c049" },
  miss:       { label: "Oportunidad perdida",  sym: "✕",  color: "#ff7769" },
  mistake:    { label: "Error",                sym: "?",  color: "#e58f2a" },
  blunder:    { label: "Blunder",              sym: "??", color: "#fa412d" },
};
const CLS_ORDER = ["brilliant", "great", "best", "excellent", "good", "book",
                   "inaccuracy", "miss", "mistake", "blunder"];

const state = {
  game: null, moves: [], summary: null, ply: 0, orientation: "white", showBest: false,
  puzzles: [], puzzleIdx: 0, puzzleSelectedSq: null, puzzleSolved: false, puzzleAttemptedCurrent: false,
  puzzleScore: { solved: 0, attempted: 0 },
};

async function loadHealth() {
  try {
    const h = await api("/api/health");
    const inp = $("#input-user");
    if (inp && h.user && !inp.value) inp.value = h.user;
    const banner = $("#engine-banner");
    if (banner) {
      const eng = h.stockfish ? "Stockfish UCI" : "Motor heurístico local (python-chess)";
      const coach = h.gemini ? "Gemini IA" : "Entrenador offline local";
      banner.textContent = `Motor activo: ${eng} · Coach: ${coach}`;
    }
  } catch (e) { /* silencioso si aún arranca */ }
}

/* ---------------- Lista de partidas ---------------- */
async function loadGames() {
  const list = $("#games-list");
  list.innerHTML = '<p class="empty">Cargando…</p>';
  let games;
  try { games = await api("/api/games"); }
  catch (e) { list.innerHTML = '<p class="empty">No se pudo conectar con el backend.</p>'; return; }

  if (!games.length) {
    list.innerHTML = '<p class="empty">No hay partidas. Pulsa «Descargar partidas».</p>';
    return;
  }
  list.innerHTML = "";
  const pending = games.filter((g) => !g.analyzed).length;
  const actions = $("#games-actions");
  actions.innerHTML = pending
    ? `<button id="btn-analyze-all" class="btn">Analizar ${pending} pendientes</button> <span id="batch-status" class="muted"></span>`
    : "";
  if (pending) $("#btn-analyze-all").onclick = analyzeAllPending;
  for (const g of games) {
    const opp = g.user_color === "white" ? g.black : g.white;
    const youColor = g.user_color === "white" ? "⚪" : "⚫";
    const resTag = g.result === "win" ? '<span class="res win">Victoria</span>'
      : g.result === "lose" ? '<span class="res lose">Derrota</span>'
      : '<span class="res draw">Tablas</span>';
    const date = g.end_time ? new Date(g.end_time * 1000).toLocaleDateString() : "";
    const stats = g.analyzed
      ? `<span class="stats">Precisión ${g.accuracy ?? "—"}% · ${g.blunders ?? 0} blunders</span>`
      : '<span class="stats pending">sin analizar</span>';
    const el = document.createElement("div");
    el.className = "game-card";
    el.innerHTML = `<div class="gc-top">${youColor} vs <b>${opp}</b> ${resTag}</div>
                    <div class="gc-bot">${g.time_class || ""} · ${date} · ${stats}</div>`;
    el.onclick = () => openGame(g.id);
    list.appendChild(el);
  }
}

async function analyzeAllPending() {
  const btn = $("#btn-analyze-all");
  const status = $("#batch-status");
  if (btn) btn.disabled = true;
  const games = await api("/api/games");
  const pend = games.filter((g) => !g.analyzed);
  for (let i = 0; i < pend.length; i++) {
    if (status) status.textContent = `Analizando ${i + 1}/${pend.length}… (no cierres esta pestaña)`;
    try { await api("/api/game/analyze?id=" + encodeURIComponent(pend[i].id), { method: "POST" }); }
    catch (e) { /* salta la que falle y continúa */ }
  }
  if (status) status.textContent = "¡Listo!";
  loadGames();
}

/* ---------------- Vista de partida ---------------- */
async function openGame(id) {
  let data = await api("/api/game?id=" + encodeURIComponent(id));
  state.game = data.game;
  state.moves = data.moves;
  state.summary = data.summary;
  state.ply = 0;
  // Por defecto, orienta el tablero a tu perspectiva (tus piezas abajo).
  state.orientation = data.game.user_color === "black" ? "black" : "white";
  state.showBest = false;
  showView("game");
  $("#btn-show-best").classList.remove("active");
  renderGameHeader();
  renderMoveList();
  renderCoach();
  goTo(0);

  // Análisis automático con Stockfish si la partida aún no está analizada.
  if (!state.game.analyzed) {
    setStatus("Analizando con Stockfish… (puede tardar ~1 min)");
    try {
      await api("/api/game/analyze?id=" + encodeURIComponent(id), { method: "POST" });
      data = await api("/api/game?id=" + encodeURIComponent(id));
      state.game = data.game;
      state.moves = data.moves;
      state.summary = data.summary;
      renderGameHeader();
      renderMoveList();
      goTo(state.ply);
    } catch (e) { setStatus("No se pudo analizar: " + e.message); return; }
  }

  // Comentario del entrenador automático (una sola vez; se cachea en la BBDD).
  if (state.game.analyzed && !(state.summary && state.summary.coach_note)) {
    setStatus("Generando comentario del entrenador…");
    try {
      const r = await api("/api/game/coach?id=" + encodeURIComponent(id), { method: "POST" });
      state.summary = state.summary || {};
      state.summary.coach_note = r.coach_note;
      renderCoach();
    } catch (e) { /* sin coach no pasa nada */ }
  }
  clearStatus();
}

function renderGameHeader() {
  const g = state.game, s = state.summary;
  $("#game-title").textContent = `${g.white} vs ${g.black}`;
  const resTxt = g.result === "win" ? "Victoria" : g.result === "lose" ? "Derrota" : "Tablas";
  let txt = `Jugaste con ${g.user_color === "white" ? "blancas" : "negras"} · ${resTxt}`;
  if (s) txt += ` · Precisión ${s.accuracy}%`;
  const op = openingName(g);
  if (op) txt += ` · ${op}`;
  $("#game-sub").textContent = txt;

  // Resumen de clasificaciones (solo tus jugadas), tipo informe de Chess.com.
  const counts = {};
  for (const m of state.moves) if (m.is_user_move) counts[m.classification] = (counts[m.classification] || 0) + 1;
  const box = $("#game-counts");
  box.innerHTML = "";
  for (const k of CLS_ORDER) {
    if (!counts[k]) continue;
    const c = CLS[k];
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.style.borderColor = c.color;
    chip.innerHTML = `<span style="color:${c.color};font-weight:800">${c.sym}</span> ${counts[k]} ${c.label}`;
    box.appendChild(chip);
  }
  if (box.children.length) {
    const lbl = document.createElement("span");
    lbl.className = "counts-label";
    lbl.textContent = "Tus jugadas:";
    box.prepend(lbl);
  }
}

function openingName(g) {
  if (g.eco_url) {
    const seg = g.eco_url.replace(/\/$/, "").split("/").pop();
    if (seg) return seg.replace(/-/g, " ") + (g.eco ? ` (${g.eco})` : "");
  }
  return g.eco || "";
}

/* ---------------- Tablero ---------------- */
function fenToBoard(fen) {
  return fen.split(" ")[0].split("/").map((row) => {
    const r = [];
    for (const ch of row) {
      if (/\d/.test(ch)) for (let i = 0; i < +ch; i++) r.push("");
      else r.push(ch);
    }
    return r;
  });
}
const sqName = (f, rTop) => "abcdefgh"[f] + (8 - rTop);

function renderBoard(fen, move) {
  const b = fenToBoard(fen);
  const board = $("#board");
  board.innerHTML = "";
  const uci = move ? move.uci : null;
  const from = uci ? uci.slice(0, 2) : null;
  const to = uci ? uci.slice(2, 4) : null;
  const flip = state.orientation === "black";

  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const r = flip ? 7 - row : row;   // fila desde arriba (0 = fila 8)
      const f = flip ? 7 - col : col;   // columna (0 = a)
      const sq = document.createElement("div");
      sq.className = "square " + ((r + f) % 2 === 0 ? "light" : "dark");
      const name = sqName(f, r);
      if (name === from || name === to) sq.classList.add("hl");

      const p = b[r][f];
      if (p) {
        const img = document.createElement("img");
        img.className = "piece";
        img.draggable = false;
        img.alt = p;
        img.src = PIECE_BASE + (p === p.toUpperCase() ? "w" : "b") + p.toUpperCase() + ".svg";
        sq.appendChild(img);
      }
      if (name === to && move && CLS[move.classification]) {
        const c = CLS[move.classification];
        const badge = document.createElement("span");
        badge.className = "sq-badge";
        badge.style.background = c.color;
        badge.textContent = c.sym;
        sq.appendChild(badge);
      }
      if (row === 7) sq.appendChild(coordEl("file", "abcdefgh"[f]));
      if (col === 0) sq.appendChild(coordEl("rank", 8 - r));
      board.appendChild(sq);
    }
  }
}

function coordEl(kind, txt) {
  const s = document.createElement("span");
  s.className = "coord " + kind;
  s.textContent = txt;
  return s;
}

function goTo(ply) {
  ply = Math.max(0, Math.min(state.moves.length, ply));
  state.ply = ply;
  let fen = START_FEN, move = null;
  if (ply === 0) {
    fen = state.moves.length ? state.moves[0].fen_before : START_FEN;
  } else {
    move = state.moves[ply - 1];
    fen = move.fen_after || move.fen_before || START_FEN;
  }
  renderBoard(fen, move);
  renderEval(ply);
  renderMoveInfo(ply);
  highlightMoveList(ply);
  drawArrows(ply);
  renderEvalGraph();
  $("#btn-move-coach").classList.toggle("hidden", ply < 1);
  $("#move-coach").classList.add("hidden");
}

/* Flechas: verde = lo que debiste jugar (en errores); azul = mejor jugada actual (botón). */
function drawArrows(ply) {
  const svg = $("#arrows");
  svg.innerHTML = "";
  if (ply >= 1) {
    const m = state.moves[ply - 1];
    if (m.best_uci && m.best_uci !== m.uci &&
        ["inaccuracy", "miss", "mistake", "blunder"].includes(m.classification)) {
      drawArrow(svg, m.best_uci.slice(0, 2), m.best_uci.slice(2, 4), ARROW_COLOR);
    }
  }
  if (state.showBest && ply < state.moves.length) {
    const best = state.moves[ply].best_uci;
    if (best) drawArrow(svg, best.slice(0, 2), best.slice(2, 4), BEST_COLOR);
  }
}

function drawArrow(svg, fromSq, toSq, color, flip = state.orientation === "black") {
  const NS = "http://www.w3.org/2000/svg";
  const center = (s) => {
    let x = "abcdefgh".indexOf(s[0]) + 0.5;
    let y = 8 - +s[1] + 0.5;
    if (flip) { x = 8 - x; y = 8 - y; }
    return [x, y];
  };
  const [x1, y1] = center(fromSq);
  const [x2, y2] = center(toSq);
  const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len;
  const headLen = 0.5, headW = 0.28, shaftW = 0.15;
  const tipX = x2 - ux * 0.06, tipY = y2 - uy * 0.06;
  const baseX = tipX - ux * headLen, baseY = tipY - uy * headLen;
  const px = -uy, py = ux;

  const line = document.createElementNS(NS, "line");
  line.setAttribute("x1", x1); line.setAttribute("y1", y1);
  line.setAttribute("x2", baseX); line.setAttribute("y2", baseY);
  line.setAttribute("stroke", color);
  line.setAttribute("stroke-width", shaftW);
  line.setAttribute("stroke-linecap", "round");
  svg.appendChild(line);

  const poly = document.createElementNS(NS, "polygon");
  poly.setAttribute("points",
    `${tipX},${tipY} ${baseX + px * headW},${baseY + py * headW} ${baseX - px * headW},${baseY - py * headW}`);
  poly.setAttribute("fill", color);
  svg.appendChild(poly);
}

function renderEval(ply) {
  const cp = ply >= 1 ? (state.moves[ply - 1].eval_cp ?? 0) : 0;
  const clamped = Math.max(-1000, Math.min(1000, cp));
  const whiteFrac = 1 / (1 + Math.exp(-0.00368 * clamped));
  $("#evalbar-white").style.height = whiteFrac * 100 + "%";
  let txt;
  if (cp >= 2000) txt = "+M";          // mate o ventaja decisiva para las blancas
  else if (cp <= -2000) txt = "−M";    // mate o ventaja decisiva para las negras
  else { const v = cp / 100; txt = (v > 0 ? "+" : "") + v.toFixed(2); }
  $("#eval-num").textContent = txt;
}

/* Gráfica de evaluación de toda la partida (clic para saltar a una jugada). */
function renderEvalGraph() {
  const wrap = $("#eval-graph-wrap");
  const n = state.moves.length;
  if (!n || !state.game || !state.game.analyzed) { wrap.innerHTML = ""; return; }
  const W = 100, H = 32, mid = H / 2;
  const yOf = (cp) => mid - (Math.max(-1000, Math.min(1000, cp || 0)) / 1000) * mid;
  const xOf = (ply) => (ply / n) * W;
  let pts = `0,${mid.toFixed(2)}`;
  state.moves.forEach((m, i) => { pts += ` ${xOf(i + 1).toFixed(2)},${yOf(m.eval_cp).toFixed(2)}`; });
  const markX = xOf(state.ply).toFixed(2);
  wrap.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" class="eval-graph">` +
    `<line x1="0" y1="${mid}" x2="${W}" y2="${mid}" class="eg-mid"/>` +
    `<polyline points="${pts}" class="eg-line"/>` +
    `<line x1="${markX}" y1="0" x2="${markX}" y2="${H}" class="eg-mark"/>` +
    `</svg>`;
  wrap.querySelector("svg").onclick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    goTo(Math.round(((e.clientX - rect.left) / rect.width) * n));
  };
}

function renderMoveInfo(ply) {
  const info = $("#move-info");
  if (ply === 0) {
    info.innerHTML = "";
    return;
  }
  const m = state.moves[ply - 1];
  const c = CLS[m.classification] || { label: m.classification, sym: "·", color: "#888" };
  const evalTxt = (m.eval_cp / 100 > 0 ? "+" : "") + (m.eval_cp / 100).toFixed(2);
  const num = `${m.move_number}${m.color === "white" ? "." : "..."}`;
  let html = `<span class="badge" style="background:${c.color}">${c.sym}</span> ` +
    `<b>${num} ${m.san}</b> — <span style="color:${c.color};font-weight:600">${c.label}</span> · eval ${evalTxt}`;
  if (["inaccuracy", "miss", "mistake", "blunder"].includes(m.classification) && m.best_san) {
    html += `<div class="best">💡 Lo mejor era <b>${m.best_san}</b> (perdiste ${(m.cp_loss / 100).toFixed(2)} de ventaja)</div>`;
  }
  info.innerHTML = html;
}

/* ---------------- Lista de jugadas (dos columnas, estilo Chess.com) ---------------- */
function renderMoveList() {
  const ml = $("#move-list");
  ml.innerHTML = "";
  let row = null;
  state.moves.forEach((m, i) => {
    if (m.color === "white") {
      row = mlRow(m.move_number + ".");
      row.append(moveCell(m, i), document.createElement("span"));
      ml.appendChild(row);
    } else {
      if (!row) {
        row = mlRow(m.move_number + "...");
        row.append(document.createElement("span"), document.createElement("span"));
        ml.appendChild(row);
      }
      row.replaceChild(moveCell(m, i), row.children[2]);
    }
  });
}

function mlRow(numText) {
  const row = document.createElement("div");
  row.className = "ml-row";
  const num = document.createElement("span");
  num.className = "ml-num";
  num.textContent = numText;
  row.appendChild(num);
  return row;
}

function moveCell(m, i) {
  const cell = document.createElement("span");
  cell.className = "ml-mv" + (m.is_user_move ? " mine" : "");
  cell.dataset.ply = i + 1;
  const c = CLS[m.classification];
  cell.innerHTML = m.san + (c && c.sym ? ` <span class="mv-sym" style="color:${c.color}">${c.sym}</span>` : "");
  cell.onclick = () => goTo(i + 1);
  return cell;
}

function highlightMoveList(ply) {
  const ml = $("#move-list");
  ml.querySelectorAll(".ml-mv").forEach((e) =>
    e.classList.toggle("active", +e.dataset.ply === ply));
  const act = ml.querySelector(".ml-mv.active");
  if (!act) return;
  ml.scrollTop = Math.max(0, act.offsetTop - ml.clientHeight / 2 + act.clientHeight / 2);
}

/* ---------------- Coach ---------------- */
function renderCoach() {
  const note = state.summary && state.summary.coach_note;
  $("#coach-text").innerHTML = note ? mdToHtml(note) : "";
  $("#coach-box").classList.toggle("hidden", !note);
}

/* Mini-renderizador de Markdown: **negrita**, listas numeradas y con guion. */
function mdToHtml(md) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  let html = "", list = null;
  const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
  for (const raw of md.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) { closeList(); continue; }
    let m;
    if ((m = line.match(/^(\d+)[.)]\s+(.*)$/))) {
      if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; }
      html += `<li>${inline(m[2])}</li>`;
    } else if ((m = line.match(/^[-*]\s+(.*)$/))) {
      if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; }
      html += `<li>${inline(m[1])}</li>`;
    } else {
      closeList();
      html += `<p>${inline(line)}</p>`;
    }
  }
  closeList();
  return html;
}

/* ---------------- Utilidades de botones ---------------- */
function setBusy(sel, txt) {
  const b = $(sel);
  b.dataset.orig = b.textContent;
  b.disabled = true;
  b.textContent = txt;
}
function unsetBusy(sel) {
  const b = $(sel);
  b.disabled = false;
  if (b.dataset.orig) b.textContent = b.dataset.orig;
}

function setStatus(txt) {
  const s = $("#status");
  s.textContent = txt;
  s.classList.remove("hidden");
}
function clearStatus() {
  $("#status").classList.add("hidden");
}

/* ---------------- Eventos ---------------- */
$("#btn-back").onclick = () => {
  $("#game-view").classList.add("hidden");
  $("#games-view").classList.remove("hidden");
  loadGames();
};

async function fetchGamesFromChessCom(triggerBtnSel) {
  const user = ($("#input-user")?.value || "").trim();
  setBusy(triggerBtnSel, "Descargando…");
  try {
    const r = await api("/api/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ months: 1, username: user || undefined }),
    });
    await loadGames();
    alert("Guardadas " + r.saved + " partidas de " + (r.user || "Chess.com") + ".");
  } catch (e) {
    alert("Error al descargar: " + e.message);
  } finally {
    unsetBusy(triggerBtnSel);
  }
}

$("#btn-fetch").onclick = () => fetchGamesFromChessCom("#btn-fetch");
if ($("#btn-fetch-user")) {
  $("#btn-fetch-user").onclick = () => fetchGamesFromChessCom("#btn-fetch-user");
}
if ($("#btn-import-pgn")) {
  $("#btn-import-pgn").onclick = () => $("#pgn-modal").classList.toggle("hidden");
  $("#btn-pgn-cancel").onclick = () => $("#pgn-modal").classList.add("hidden");
  $("#btn-pgn-submit").onclick = async () => {
    const pgn = ($("#input-pgn").value || "").trim();
    const user_color = $("#select-pgn-color").value;
    const username = ($("#input-user")?.value || "Jugador").trim();
    if (!pgn) return alert("Pega primero un PGN.");
    setBusy("#btn-pgn-submit", "Importando…");
    try {
      const r = await api("/api/games/import-pgn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pgn, user_color, username }),
      });
      $("#input-pgn").value = "";
      $("#pgn-modal").classList.add("hidden");
      await loadGames();
      if (r.id) openGame(r.id);
    } catch (e) {
      alert("PGN inválido: " + e.message);
    } finally {
      unsetBusy("#btn-pgn-submit");
    }
  };
}
if ($("#btn-demo-game")) {
  $("#btn-demo-game").onclick = async () => {
    setBusy("#btn-demo-game", "Cargando…");
    try {
      const r = await api("/api/games/demo", { method: "POST" });
      await loadGames();
      if (r.id) openGame(r.id);
    } catch (e) {
      alert("No se pudo crear la partida demo: " + e.message);
    } finally {
      unsetBusy("#btn-demo-game");
    }
  };
}

const moveCoachCache = {};
$("#btn-move-coach").onclick = async () => {
  if (state.ply < 1) return;
  const key = state.game.id + ":" + state.ply;
  const box = $("#move-coach");
  if (moveCoachCache[key]) {
    box.innerHTML = mdToHtml(moveCoachCache[key]);
    box.classList.remove("hidden");
    return;
  }
  setBusy("#btn-move-coach", "Pensando…");
  try {
    const r = await api(
      `/api/game/move-coach?id=${encodeURIComponent(state.game.id)}&ply=${state.ply}`,
      { method: "POST" }
    );
    moveCoachCache[key] = r.explanation;
    box.innerHTML = mdToHtml(r.explanation);
    box.classList.remove("hidden");
  } catch (e) { alert("Error con el coach: " + e.message); }
  finally { unsetBusy("#btn-move-coach"); }
};

$("#btn-start").onclick = () => goTo(0);
$("#btn-prev").onclick = () => goTo(state.ply - 1);
$("#btn-next").onclick = () => goTo(state.ply + 1);
$("#btn-end").onclick = () => goTo(state.moves.length);
$("#btn-flip").onclick = () => {
  state.orientation = state.orientation === "white" ? "black" : "white";
  goTo(state.ply);
};

$("#btn-show-best").onclick = () => {
  state.showBest = !state.showBest;
  $("#btn-show-best").classList.toggle("active", state.showBest);
  drawArrows(state.ply);
};

const ERR_SET = ["inaccuracy", "miss", "mistake", "blunder"];
function gotoError(dir) {
  const ms = state.moves;
  if (dir > 0) {
    for (let p = state.ply + 1; p <= ms.length; p++)
      if (ms[p - 1].is_user_move && ERR_SET.includes(ms[p - 1].classification)) return goTo(p);
  } else {
    for (let p = state.ply - 1; p >= 1; p--)
      if (ms[p - 1].is_user_move && ERR_SET.includes(ms[p - 1].classification)) return goTo(p);
  }
}
$("#btn-prev-err").onclick = () => gotoError(-1);
$("#btn-next-err").onclick = () => gotoError(1);

document.addEventListener("keydown", (e) => {
  if ($("#game-view").classList.contains("hidden")) return;
  if (e.key === "ArrowLeft") goTo(state.ply - 1);
  if (e.key === "ArrowRight") goTo(state.ply + 1);
});

/* ---------------- Navegación / Estadísticas ---------------- */
function showView(name) {
  $("#games-view").classList.toggle("hidden", name !== "games");
  $("#game-view").classList.toggle("hidden", name !== "game");
  $("#stats-view").classList.toggle("hidden", name !== "stats");
  $("#train-view").classList.toggle("hidden", name !== "train");
  window.scrollTo(0, 0);
}

$("#brand").onclick = () => { showView("games"); loadGames(); };
$("#btn-stats").onclick = () => { showView("stats"); loadStats(); };
$("#btn-stats-back").onclick = () => { showView("games"); loadGames(); };
$("#btn-train").onclick = () => { showView("train"); loadPuzzles(); };
$("#btn-train-back").onclick = () => { showView("games"); loadGames(); };

async function loadStats() {
  const c = $("#stats-content");
  c.innerHTML = '<p class="empty">Calculando…</p>';
  try { renderStats(await api("/api/stats")); }
  catch (e) { c.innerHTML = '<p class="empty">No se pudieron cargar las estadísticas.</p>'; }
}

function renderStats(d) {
  const wld = (x) => `${x.wins}V / ${x.draws}T / ${x.losses}D`;
  const pct = (x) => (x.games ? Math.round((100 * x.wins) / x.games) : 0);
  const t = d.totals;
  let h = "";

  h += `<div class="stat-cards">
    <div class="stat-card"><div class="sc-num">${t.games}</div><div class="sc-lbl">Partidas (${t.analyzed} analizadas)</div></div>
    <div class="stat-card"><div class="sc-num">${t.accuracy ?? "—"}%</div><div class="sc-lbl">Precisión media</div></div>
    <div class="stat-card"><div class="sc-num">${t.avg_acpl ?? "—"}</div><div class="sc-lbl">ACPL medio</div></div>
    <div class="stat-card"><div class="sc-num">${pct(t)}%</div><div class="sc-lbl">${wld(t)}</div></div>
  </div>`;

  if (d.best_game) {
    h += `<div class="stat-cards">
      <div class="stat-card"><div class="sc-num" style="color:var(--good)">${d.best_game.accuracy}%</div><div class="sc-lbl">Mejor partida (vs ${d.best_game.opponent})</div></div>
      <div class="stat-card"><div class="sc-num" style="color:var(--blunder)">${d.worst_game.accuracy}%</div><div class="sc-lbl">Peor partida (vs ${d.worst_game.opponent})</div></div>
    </div>`;
  }

  h += `<h3>Rendimiento por color</h3><div class="stat-cards">
    <div class="stat-card"><div class="sc-num">⚪ ${pct(d.by_color.white)}%</div><div class="sc-lbl">${wld(d.by_color.white)} · ${d.by_color.white.accuracy ?? "—"}%</div></div>
    <div class="stat-card"><div class="sc-num">⚫ ${pct(d.by_color.black)}%</div><div class="sc-lbl">${wld(d.by_color.black)} · ${d.by_color.black.accuracy ?? "—"}%</div></div>
  </div>`;

  h += `<h3>Por modalidad</h3><div class="table-wrap"><table class="stat-table">
    <tr><th>Modalidad</th><th>Partidas</th><th>V/T/D</th><th>Precisión</th></tr>`;
  for (const [k, v] of Object.entries(d.by_time)) {
    h += `<tr><td>${k}</td><td>${v.games}</td><td>${v.wins}/${v.draws}/${v.losses}</td><td>${v.accuracy ?? "—"}%</td></tr>`;
  }
  h += `</table></div>`;

  h += `<h3>Tus jugadas (todas las partidas)</h3><div class="counts">`;
  for (const k of CLS_ORDER) {
    if (!d.classifications[k]) continue;
    const c = CLS[k];
    h += `<span class="chip" style="border-color:${c.color}"><span style="color:${c.color};font-weight:800">${c.sym}</span> ${d.classifications[k]} ${c.label}</span>`;
  }
  h += `</div>`;

  const phLabel = { opening: "Apertura", middlegame: "Medio juego", endgame: "Final" };
  h += `<h3>¿En qué fase fallas más?</h3><div class="table-wrap"><table class="stat-table">
    <tr><th>Fase</th><th>Jugadas</th><th>ACPL</th><th>?!</th><th>?</th><th>??</th></tr>`;
  for (const ph of ["opening", "middlegame", "endgame"]) {
    const p = d.phases[ph];
    h += `<tr><td>${phLabel[ph]}</td><td>${p.moves}</td><td>${p.acpl}</td><td>${p.inaccuracies}</td><td>${p.mistakes}</td><td style="color:${p.blunders ? "var(--blunder)" : "inherit"}">${p.blunders}</td></tr>`;
  }
  h += `</table></div>`;

  h += `<h3>Tus aperturas</h3><div class="table-wrap"><table class="stat-table">
    <tr><th>Apertura</th><th>Partidas</th><th>V/T/D</th><th>Precisión</th></tr>`;
  for (const o of d.openings) {
    h += `<tr><td class="op-name" title="${o.opening}">${o.opening}</td><td>${o.games}</td><td>${o.wins}/${o.draws}/${o.losses}</td><td>${o.accuracy ?? "—"}%</td></tr>`;
  }
  h += `</table></div>`;

  $("#stats-content").innerHTML = h;
}

/* ---------------- Entrenamiento táctico ---------------- */
async function loadPuzzles() {
  const c = $("#train-content");
  c.innerHTML = '<p class="empty">Cargando…</p>';
  try {
    state.puzzles = await api("/api/puzzles");
    state.puzzleIdx = 0;
    state.puzzleSelectedSq = null;
    state.puzzleSolved = false;
    state.puzzleAttemptedCurrent = false;
    renderPuzzle();
  } catch (e) {
    c.innerHTML = '<p class="empty">No se pudieron cargar los ejercicios.</p>';
  }
}

function buildBoardInto(boardEl, svgEl, fen, flip, arrowUci, opts = {}) {
  const b = fenToBoard(fen);
  boardEl.innerHTML = "";
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      const r = flip ? 7 - row : row;
      const f = flip ? 7 - col : col;
      const sqNameStr = sqName(f, r);
      const sq = document.createElement("div");
      sq.className = "square " + ((r + f) % 2 === 0 ? "light" : "dark");
      if (opts.selectedSq === sqNameStr) sq.classList.add("selected-sq");
      sq.dataset.sq = sqNameStr;
      const p = b[r][f];
      if (p) {
        const img = document.createElement("img");
        img.className = "piece";
        img.draggable = false;
        img.src = PIECE_BASE + (p === p.toUpperCase() ? "w" : "b") + p.toUpperCase() + ".svg";
        sq.appendChild(img);
      }
      if (row === 7) sq.appendChild(coordEl("file", "abcdefgh"[f]));
      if (col === 0) sq.appendChild(coordEl("rank", 8 - r));
      if (opts.onSquareClick) {
        sq.onclick = () => opts.onSquareClick(sqNameStr, p);
      }
      boardEl.appendChild(sq);
    }
  }
  svgEl.innerHTML = "";
  if (arrowUci) drawArrow(svgEl, arrowUci.slice(0, 2), arrowUci.slice(2, 4), BEST_COLOR, flip);
}

function renderPuzzle() {
  const ps = state.puzzles;
  const c = $("#train-content");
  if (!ps || !ps.length) {
    c.innerHTML = '<p class="empty">Aún no hay errores para entrenar. Abre y analiza más partidas.</p>';
    return;
  }
  const i = state.puzzleIdx;
  const p = ps[i];
  const flip = p.side_to_move === "b";
  const sideTxt = p.side_to_move === "w" ? "blancas" : "negras";
  const label = (CLS[p.classification] || { label: p.classification }).label.toLowerCase();
  const score = state.puzzleScore;
  c.innerHTML = `
    <p class="sub">Ejercicio ${i + 1} / ${ps.length} · de tu partida vs ${p.opponent} · <b id="train-score">Aciertos: ${score.solved} / ${score.attempted}</b></p>
    <div class="board-row">
      <div class="board-wrap">
        <div id="train-board"></div>
        <svg id="train-arrows" viewBox="0 0 8 8" preserveAspectRatio="none"></svg>
      </div>
    </div>
    <div class="move-info">Juegan <b>${sideTxt}</b>. Haz clic en pieza origen y casilla destino para encontrar la mejor jugada.
      <span class="muted">(en la partida jugaste ${p.played_san}, un ${label})</span></div>
    <div id="puzzle-solution"></div>
    <div class="tools">
      <button id="btn-solution" class="btn">Mostrar solución</button>
      <button id="btn-next-puzzle" class="btn">Siguiente ▶</button>
    </div>`;

  const isFriendly = (piece) =>
    !!piece && (p.side_to_move === "w" ? piece === piece.toUpperCase() : piece === piece.toLowerCase());

  const drawPuzzleBoard = (arrowUci = null) => {
    buildBoardInto($("#train-board"), $("#train-arrows"), p.fen, flip, arrowUci, {
      selectedSq: state.puzzleSelectedSq,
      onSquareClick: (sq, piece) => {
        if (state.puzzleSolved) return;
        if (!state.puzzleSelectedSq) {
          if (isFriendly(piece)) {
            state.puzzleSelectedSq = sq;
            drawPuzzleBoard();
          }
          return;
        }
        if (state.puzzleSelectedSq === sq) {
          state.puzzleSelectedSq = null;
          drawPuzzleBoard();
          return;
        }
        if (isFriendly(piece)) {
          state.puzzleSelectedSq = sq;
          drawPuzzleBoard();
          return;
        }
        const fromSq = state.puzzleSelectedSq;
        const attempt = fromSq + sq;
        const target = (p.solution_uci || "").slice(0, 4);
        if (!state.puzzleAttemptedCurrent) {
          state.puzzleAttemptedCurrent = true;
          state.puzzleScore.attempted += 1;
        }
        if (attempt === target) {
          state.puzzleSolved = true;
          state.puzzleSelectedSq = null;
          state.puzzleScore.solved += 1;
          $("#train-score").textContent = `Aciertos: ${state.puzzleScore.solved} / ${state.puzzleScore.attempted}`;
          drawPuzzleBoard(p.solution_uci);
          $("#puzzle-solution").innerHTML =
            `<div class="move-coach good-msg">✅ ¡Correcto! La mejor jugada era <b>${p.solution_san}</b>.</div>`;
        } else {
          state.puzzleSelectedSq = null;
          drawPuzzleBoard();
          $("#train-score").textContent = `Aciertos: ${state.puzzleScore.solved} / ${state.puzzleScore.attempted}`;
          $("#puzzle-solution").innerHTML =
            `<div class="move-coach bad-msg">❌ Jugada ${fromSq}→${sq} no es la mejor. ¡Prueba otra o pulsa Mostrar solución!</div>`;
        }
      },
    });
  };

  drawPuzzleBoard();
  $("#btn-solution").onclick = () => {
    state.puzzleSolved = true;
    state.puzzleSelectedSq = null;
    drawPuzzleBoard(p.solution_uci);
    $("#puzzle-solution").innerHTML =
      `<div class="move-coach">✅ La mejor jugada era <b>${p.solution_san}</b>.</div>`;
  };
  $("#btn-next-puzzle").onclick = () => {
    state.puzzleIdx = (i + 1) % ps.length;
    state.puzzleSelectedSq = null;
    state.puzzleSolved = false;
    state.puzzleAttemptedCurrent = false;
    renderPuzzle();
  };
}

/* ---------------- Init ---------------- */
loadHealth();
loadGames();
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
