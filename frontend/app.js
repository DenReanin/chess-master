"use strict";

const $ = (s) => document.querySelector(s);
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

const PIECE_BASE = "/pieces/cburnett/";
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const ARROW_COLOR = "rgba(20, 160, 80, .9)";

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

const state = { game: null, moves: [], summary: null, ply: 0, orientation: "white" };

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

/* ---------------- Vista de partida ---------------- */
async function openGame(id) {
  const data = await api("/api/game?id=" + encodeURIComponent(id));
  state.game = data.game;
  state.moves = data.moves;
  state.summary = data.summary;
  state.ply = 0;
  // Por defecto, orienta el tablero a tu perspectiva (tus piezas abajo).
  state.orientation = data.game.user_color === "black" ? "black" : "white";
  $("#games-view").classList.add("hidden");
  $("#game-view").classList.remove("hidden");
  window.scrollTo(0, 0);
  renderGameHeader();
  renderMoveList();
  renderCoach();
  updateActions();
  goTo(0);
}

function renderGameHeader() {
  const g = state.game, s = state.summary;
  $("#game-title").textContent = `${g.white} vs ${g.black}`;
  const resTxt = g.result === "win" ? "Victoria" : g.result === "lose" ? "Derrota" : "Tablas";
  let txt = `Jugaste con ${g.user_color === "white" ? "blancas" : "negras"} · ${resTxt}`;
  if (s) txt += ` · Precisión ${s.accuracy}%`;
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
  drawBestArrow(ply);
}

/* Flecha verde de la mejor jugada, solo cuando la jugada fue subóptima. */
function drawBestArrow(ply) {
  const svg = $("#arrows");
  svg.innerHTML = "";
  if (ply < 1) return;
  const m = state.moves[ply - 1];
  if (!m.best_uci || m.best_uci === m.uci) return;
  if (!["inaccuracy", "miss", "mistake", "blunder"].includes(m.classification)) return;
  drawArrow(svg, m.best_uci.slice(0, 2), m.best_uci.slice(2, 4), ARROW_COLOR);
}

function drawArrow(svg, fromSq, toSq, color) {
  const NS = "http://www.w3.org/2000/svg";
  const flip = state.orientation === "black";
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
  const val = cp / 100;
  $("#eval-num").textContent = (val > 0 ? "+" : "") + val.toFixed(2);
}

function renderMoveInfo(ply) {
  const info = $("#move-info");
  if (ply === 0) {
    info.innerHTML = '<span class="muted">Posición inicial. Usa ▶ o las flechas ← → para avanzar.</span>';
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
  cell.className = "ml-mv";
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

function updateActions() {
  const analyzed = !!state.game.analyzed;
  $("#btn-analyze").textContent = analyzed ? "Reanalizar" : "Analizar partida";
  $("#btn-coach").classList.toggle("hidden", !analyzed);
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

/* ---------------- Eventos ---------------- */
$("#btn-back").onclick = () => {
  $("#game-view").classList.add("hidden");
  $("#games-view").classList.remove("hidden");
  loadGames();
};

$("#btn-fetch").onclick = async () => {
  setBusy("#btn-fetch", "Descargando…");
  try {
    const r = await api("/api/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ months: 1 }),
    });
    await loadGames();
    alert("Guardadas " + r.saved + " partidas.");
  } catch (e) { alert("Error al descargar: " + e.message); }
  finally { unsetBusy("#btn-fetch"); }
};

$("#btn-analyze").onclick = async () => {
  setBusy("#btn-analyze", "Analizando…");
  try {
    await api("/api/game/analyze?id=" + encodeURIComponent(state.game.id) + "&depth=14", { method: "POST" });
    await openGame(state.game.id);
  } catch (e) { alert("Error al analizar: " + e.message); }
  finally { unsetBusy("#btn-analyze"); }
};

$("#btn-coach").onclick = async () => {
  setBusy("#btn-coach", "Pensando…");
  try {
    const r = await api("/api/game/coach?id=" + encodeURIComponent(state.game.id), { method: "POST" });
    state.summary = state.summary || {};
    state.summary.coach_note = r.coach_note;
    renderCoach();
    $("#coach-box").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) { alert("Error con el coach: " + e.message); }
  finally { unsetBusy("#btn-coach"); }
};

$("#btn-start").onclick = () => goTo(0);
$("#btn-prev").onclick = () => goTo(state.ply - 1);
$("#btn-next").onclick = () => goTo(state.ply + 1);
$("#btn-end").onclick = () => goTo(state.moves.length);
$("#btn-flip").onclick = () => {
  state.orientation = state.orientation === "white" ? "black" : "white";
  goTo(state.ply);
};

document.addEventListener("keydown", (e) => {
  if ($("#game-view").classList.contains("hidden")) return;
  if (e.key === "ArrowLeft") goTo(state.ply - 1);
  if (e.key === "ArrowRight") goTo(state.ply + 1);
});

/* ---------------- Init ---------------- */
loadGames();
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
