"""Tema y estilos compartidos de la interfaz de aprendizaje.

Todo el CSS de la aplicación vive aquí. Las vistas usan clases e ids propios
(``#app-header``, ``.card``, ``.status-pill``…) para no depender de selectores
internos de Gradio.
"""

CSS = r"""
:root {
  --bg: #0B1220;
  --surface: #131E30;
  --surface-2: #0F1A2B;
  --surface-3: #17263A;
  --line: #2B3A50;
  --text: #F1F5F9;
  --muted: #B8C5D6;
  --accent: #5EEAD4;
  --accent-ink: #06251F;
  --green: #4ADE80;
  --amber: #FBBF24;
  --red: #FB7185;
  --blue: #7DD3FC;
  --radius: 16px;
  --radius-sm: 10px;
  --space: 16px;
  --shadow: 0 16px 40px rgba(0, 0, 0, .22);
  --font: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}

html, body {
  background: var(--bg) !important;
  overflow-x: hidden !important;
}

.gradio-container {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--font) !important;
  max-width: none !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 22px 40px !important;
  overflow-x: clip;
  box-sizing: border-box;
}

.gradio-container .prose :is(h1, h2, h3, h4, strong, b) { color: var(--text); }
.gradio-container .prose p,
.gradio-container .prose li,
.gradio-container .prose span { color: var(--muted); }
.gradio-container .prose a { color: var(--accent) !important; }

/* ── Cabecera ─────────────────────────────────────────────────────────── */
#app-header {
  border-bottom: 1px solid var(--line);
  margin: 0 0 10px;
  padding: 16px 0 14px;
}
#app-header .brand {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
#app-header .brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--accent), #2DD4BF);
  color: var(--accent-ink);
  display: grid;
  place-items: center;
  font-weight: 900;
  font-size: 1.05rem;
  flex: 0 0 auto;
}
#app-header h1 {
  color: var(--text);
  font-size: clamp(1.12rem, 2.4vw, 1.42rem);
  margin: 0;
  line-height: 1.2;
}
#app-header .tagline {
  color: var(--muted);
  margin: 2px 0 0;
  font-size: .92rem;
}
#app-header .student-note {
  margin-left: auto;
  color: var(--muted);
  font-size: .82rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 6px 11px;
  background: var(--surface);
}

/* ── Navegación principal ─────────────────────────────────────────────── */
#main-nav { border: 0 !important; background: transparent !important; }
#main-nav [role="tablist"] {
  gap: 4px;
  border-bottom: 1px solid var(--line);
  overflow-x: auto;
  flex-wrap: nowrap;
  scrollbar-width: thin;
}
#main-nav [role="tab"] {
  color: var(--muted) !important;
  border: 1px solid transparent !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 10px 10px 0 0 !important;
  padding: 10px 13px !important;
  font-weight: 650 !important;
  white-space: nowrap;
}
#main-nav [role="tab"][aria-selected="true"] {
  color: var(--text) !important;
  background: var(--surface) !important;
  border-color: var(--line) !important;
  border-bottom-color: var(--accent) !important;
}
#main-nav [role="tab"]:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }

/* ── Superficies y tipografía ─────────────────────────────────────────── */
.card,
.hero-card,
.notice-card,
.result-card,
.route-card,
.question-card,
.review-card,
.empty-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 18px;
  box-shadow: var(--shadow);
  min-width: 0;
}
.hero-card {
  background:
    radial-gradient(900px 220px at 15% -40%, rgba(94, 234, 212, .18), transparent 65%),
    linear-gradient(130deg, #162940, var(--surface));
  border-color: #31516E;
}
.result-card { border-color: #2F827B; }
.route-card { border-color: #31516E; }
.notice-card { }
.notice-danger { }
.empty-card { border-style: dashed; box-shadow: none; }

.card h2, .hero-card h2, .result-card h2, .route-card h2,
.question-card h2, .notice-card h2 { color: var(--text); margin: 0 0 8px; line-height: 1.25; }
.card h3, .hero-card h3, .result-card h3, .route-card h3,
.question-card h3, .notice-card h3 { color: var(--text); margin: 14px 0 6px; }
.card p, .hero-card p, .result-card p, .route-card p,
.question-card p, .notice-card p { color: var(--muted); margin: 6px 0; }
.muted { color: var(--muted) !important; }
.small { font-size: .86rem; }
.mono { font-family: var(--mono) !important; }
.reading { max-width: 76ch; }

.eyebrow {
  color: var(--accent);
  font-size: .78rem;
  font-weight: 800;
  letter-spacing: .07em;
  text-transform: uppercase;
}
.step-label { color: var(--accent); font-size: .78rem; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }

/* ── Píldoras de estado ───────────────────────────────────────────────── */
.status-pill,
.status-ok,
.status-warn,
.status-bad,
.status-info,
.status-neutral {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: .78rem;
  font-weight: 800;
  line-height: 1.55;
  white-space: nowrap;
}
.status-ok { color: var(--green); background: rgba(74, 222, 128, .08); }
.status-warn { color: var(--amber); background: rgba(251, 191, 36, .08); }
.status-bad { color: var(--red); background: rgba(251, 113, 133, .08); }
.status-info { color: var(--blue); background: rgba(125, 211, 252, .08); }
.status-neutral { color: var(--muted); background: rgba(184, 197, 214, .08); }

/* ── Progreso ─────────────────────────────────────────────────────────── */
.progress-wrap { margin: 12px 0 6px; }
.progress-label { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: .86rem; margin-bottom: 7px; }
progress.progress-bar {
  width: 100%;
  height: 11px;
  border: 0;
  border-radius: 999px;
  overflow: hidden;
  background: #27364A;
  appearance: none;
}
progress.progress-bar::-webkit-progress-bar { background: #27364A; border-radius: 999px; }
progress.progress-bar::-webkit-progress-value { background: var(--accent); border-radius: 999px; }
progress.progress-bar::-moz-progress-bar { background: var(--accent); border-radius: 999px; }

/* ── Botones ──────────────────────────────────────────────────────────── */
.gradio-container button {
  border-radius: var(--radius-sm) !important;
  font-weight: 700 !important;
  min-height: 42px;
  white-space: normal !important;
  line-height: 1.25 !important;
}
.gradio-container button.primary,
.gradio-container .primary {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: var(--accent-ink) !important;
}
.gradio-container button.primary:hover { filter: brightness(1.06); }
.gradio-container button.secondary {
  background: transparent !important;
  border-color: #5D7088 !important;
  color: var(--text) !important;
}
.gradio-container button.stop {
  background: var(--red) !important;
  border-color: var(--red) !important;
  color: #2A0A11 !important;
}
.gradio-container button:focus-visible,
.gradio-container input:focus-visible,
.gradio-container textarea:focus-visible,
.gradio-container select:focus-visible,
.gradio-container [role="tab"]:focus-visible {
  outline: 3px solid var(--accent) !important;
  outline-offset: 2px !important;
}
.button-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.button-row > * { flex: 0 1 auto; }

a.button-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 9px 14px;
  border: 1px solid #5D7088;
  border-radius: var(--radius-sm);
  color: var(--text) !important;
  background: transparent;
  text-decoration: none;
  font-weight: 700;
}
a.button-link.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink) !important; }
a.button-link:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }

/* ── Formularios y componentes Gradio ─────────────────────────────────── */
.gradio-container .block,
.gradio-container .form {
  background: transparent !important;
  border-color: var(--line) !important;
}
.gradio-container input,
.gradio-container textarea,
.gradio-container select {
  background: var(--surface-2) !important;
  color: var(--text) !important;
  border-color: var(--line) !important;
}
.gradio-container .label-wrap,
.gradio-container .label-wrap span { color: var(--muted) !important; }
.gradio-container .wrap { border-color: var(--line) !important; }
.gradio-container .wrap .wrap { background: var(--surface-2) !important; }
.gradio-container .cm-editor { background: var(--surface-2) !important; color: var(--text) !important; }
.gradio-container .cm-gutters { background: #0C1727 !important; color: #7E93AB !important; border-color: var(--line) !important; }

/* Radios normales (Paso 2, catálogos simples): indicador de selección visible */
.gradio-container input[type="radio"] {
  accent-color: var(--accent) !important;
  width: 18px !important;
  height: 18px !important;
}
.gradio-container .wrap input[type="radio"] + span,
.gradio-container .wrap label span,
.gradio-container .wrap label { color: var(--text) !important; }
/* Label del radio seleccionado: fondo y borde distintos para que se note */
.gradio-container .wrap label:has(input[type="radio"]:checked) {
  background: rgba(94, 234, 212, .16) !important;
  border: 1px solid var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent) inset !important;
}
.gradio-container .wrap label:has(input[type="radio"]:checked) span {
  color: var(--accent) !important;
  font-weight: 700 !important;
}

/* Tarjetas del catálogo de actividades (Radio estilizado). */
.activity-cards .wrap {
  display: grid !important;
  grid-template-columns: repeat(auto-fit, minmax(245px, 1fr));
  gap: 10px;
  border: 0 !important;
  background: transparent !important;
}
.activity-cards label {
  background: var(--surface) !important;
  border: 1px solid var(--line) !important;
  border-radius: 13px !important;
  padding: 12px !important;
  min-height: 82px;
  align-items: flex-start !important;
  color: var(--text) !important;
  white-space: normal !important;
}
.activity-cards label:has(input:checked) {
  border-color: var(--accent) !important;
  background: #17333B !important;
  box-shadow: 0 0 0 1px var(--accent) inset;
}
.activity-cards label span {
  white-space: normal !important;
  overflow-wrap: anywhere;
  line-height: 1.35;
  color: var(--text) !important;
}

/* Opciones SQL largas: nunca ensanchan la página. */
.sql-choice .wrap { display: flex !important; flex-direction: column; gap: 8px; border: 0 !important; }
.sql-choice label {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px !important;
  background: var(--surface-2);
  font-family: var(--mono) !important;
  font-size: .88rem;
  white-space: pre-wrap !important;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.sql-choice label:has(input:checked) { border-color: var(--accent); background: #17333B; }
.sql-choice label span, .sql-choice label p { white-space: pre-wrap !important; overflow-wrap: anywhere; font-family: var(--mono) !important; }
.sql-choice label input { flex: 0 0 auto; }

/* ── Layouts adaptables ───────────────────────────────────────────────── */
.route-layout, .lab-layout { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
.route-layout > .route-main { flex: 1 1 340px; min-width: 0; }
.route-layout > .route-side { flex: 1 1 380px; min-width: 0; }
.lab-layout > .lab-editor { flex: 1 1 420px; min-width: 0; }
.lab-layout > .lab-reference { flex: 1 1 300px; min-width: 0; }

.entity-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 12px 0; }
.stat {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 12px;
  background: var(--surface-2);
}
.stat b { display: block; font-size: 1.15rem; color: var(--text); }
.stat span { color: var(--muted); font-size: .82rem; }

/* ── Lista de pasos ───────────────────────────────────────────────────── */
ol.steps { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 8px; }
ol.steps li {
  display: grid;
  grid-template-columns: 28px 1fr auto;
  gap: 10px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 12px;
  background: var(--surface-2);
  color: var(--text);
}
ol.steps li.is-next { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent) inset; }
ol.steps .step-index { color: var(--muted); font-weight: 800; font-size: .82rem; }
ol.steps .step-title { color: var(--text); font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
ol.steps .step-reason { color: var(--muted); font-size: .82rem; margin-top: 2px; }
/* Fila de disponibilidad de actividades: tema · estado · motivo en línea sin encimarse */
ol.steps li .fila-disponibilidad {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}
ol.steps li .fila-disponibilidad .step-title {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
ol.steps li .fila-disponibilidad .motivo {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted);
  font-size: .82rem;
}
ol.steps li .fila-disponibilidad .status-pill,
ol.steps li .fila-disponibilidad .status-ok,
ol.steps li .fila-disponibilidad .status-warn,
ol.steps li .fila-disponibilidad .status-bad,
ol.steps li .fila-disponibilidad .status-info,
ol.steps li .fila-disponibilidad .status-neutral {
  flex: 0 0 auto;
  white-space: nowrap;
}

/* ── Recursos ─────────────────────────────────────────────────────────── */
.resource-list { display: grid; gap: 8px; margin: 8px 0 0; padding: 0; list-style: none; }
.resource-list li {
  border: 1px solid var(--line);
  border-radius: 11px;
  padding: 10px 12px;
  background: var(--surface-2);
}
.resource-list a { color: var(--accent) !important; font-weight: 700; overflow-wrap: anywhere; }
.resource-meta { color: var(--muted); font-size: .82rem; }

/* ── Tablas SQL ───────────────────────────────────────────────────────── */
.table-scroll { width: 100%; max-width: 100%; overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; }
table.schema { border-collapse: collapse; width: max-content; min-width: 100%; font-size: .84rem; }
table.schema th, table.schema td { border-bottom: 1px solid var(--line); padding: 7px 9px; text-align: left; color: var(--muted); white-space: nowrap; }
table.schema th { color: var(--text); background: var(--surface-3); font-weight: 700; }
table.schema td.mono { color: var(--text); }
.schema-block { margin: 10px 0 12px; }
.schema-block h4 { color: var(--text); margin: 0 0 6px; font-size: .9rem; }

/* ── Avisos y resultados ──────────────────────────────────────────────── */
.callout { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; background: var(--surface-2); color: var(--muted); }
.callout.warn { }
.callout.bad { }
.callout.good { }
.score-line { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin: 8px 0; }
.score-line b { font-size: 2rem; color: var(--text); line-height: 1; }
.criteria-list { margin: 6px 0 0; padding-left: 20px; color: var(--muted); }
.criteria-list li { margin: 3px 0; }
.criteria-ok { color: var(--green); }
.criteria-bad { color: var(--amber); }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px; margin: 8px 0; font-size: .88rem; }
.kv dt { color: var(--muted); }
.kv dd { color: var(--text); margin: 0; overflow-wrap: anywhere; }

/* ── Zona de reinicio ─────────────────────────────────────────────────── */
.danger-zone { border: 1px solid #864352 !important; background: #2A1823 !important; border-radius: 12px; padding: 14px; }
.danger-zone .prose p, .danger-zone .prose strong { color: #FFD9E0 !important; }

/* ── Compatibilidad con Gradio ────────────────────────────────────────── */
.gradio-container footer { display: none !important; }
.gradio-container .tabs { border: 0 !important; }
.gradio-container .gap { gap: var(--space); }
.gradio-container .form { border: 0 !important; }

@media (max-width: 760px) {
  .gradio-container { padding: 0 12px 30px !important; }
  #app-header .student-note { margin-left: 0; }
  .route-layout, .lab-layout { flex-direction: column; }
  .route-layout > *, .lab-layout > * { width: 100%; flex-basis: auto; }
  .card, .hero-card, .notice-card, .result-card, .route-card, .question-card, .review-card { padding: 14px; border-radius: 13px; }
  .activity-cards .wrap { grid-template-columns: 1fr; }
  .button-row { flex-direction: column; align-items: stretch; }
  .button-row > * { width: 100%; }
  .stat-grid { grid-template-columns: 1fr 1fr; }
  ol.steps li { grid-template-columns: 24px 1fr; }
  ol.steps li .status-pill, ol.steps li .status-ok, ol.steps li .status-warn, ol.steps li .status-bad { grid-column: 2; justify-self: start; }
}

@media (max-width: 420px) {
  .gradio-container { padding: 0 9px 26px !important; }
  .stat-grid { grid-template-columns: 1fr; }
  #app-header h1 { font-size: 1.05rem; }
  #main-nav [role="tab"] { padding: 9px 9px !important; font-size: .86rem; }
}
"""
