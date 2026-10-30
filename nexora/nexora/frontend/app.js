'use strict';
/* Nexora frontend. Plain JS, no build step. Every screen reads from and writes to the REST API,
   then re-renders from the server's answer, so the UI always matches the database. */

const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const S = { token: localStorage.getItem('nexora_token'), user: null, timer: null, nav: 0, predAsset: null, alertFilter: { status: 'active', severity: '' } };

const ROUTES = [
  { id: 'overview', label: 'Overview', icon: 'house', title: 'AI Industrial Intelligence Platform', sub: 'Real-time visibility. Predictive insights. Human-approved actions.' },
  { id: 'assets', label: 'Assets', icon: 'cube', title: 'Assets', sub: 'Register, edit and retire the equipment you monitor.' },
  { id: 'telemetry', label: 'Telemetry', icon: 'wave-square', title: 'Telemetry', sub: 'Latest sensor readings. New readings update health and alerts instantly.' },
  { id: 'alerts', label: 'Alerts', icon: 'bell', title: 'Alerts', sub: 'Triage alerts, ask AI for a diagnosis, and approve what happens next.' },
  { id: 'workflows', label: 'Workflows', icon: 'diagram-project', title: 'Workflows', sub: 'The escalation steps your team follows after an alert.' },
  { id: 'analytics', label: 'Analytics', icon: 'chart-column', title: 'Analytics', sub: 'Fleet health and failure risk from sensor trends.' },
  { id: 'insights', label: 'AI Insights', icon: 'microchip', title: 'AI Insights', sub: 'Suggestions from Gemma 4. Nothing happens until a person approves it.' },
  { id: 'reports', label: 'Reports', icon: 'file-lines', title: 'Reports', sub: 'Export what the database holds.' },
  { id: 'integrations', label: 'Integrations', icon: 'plug', title: 'Integrations', sub: 'Systems your plant connects to.' },
  { id: 'settings', label: 'Settings', icon: 'sliders', title: 'Settings', sub: 'Alarm limits, KPIs and your profile.' },
];

/* ------------------------------------------------------------------ helpers */
function ago(iso) {
  if (!iso) return 'never';
  const m = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  if (m < 1) return 'just now';
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h} hr ago` : `${Math.round(h / 24)} d ago`;
}
const num = (v, d = 1) => (v === null || v === undefined ? '-' : Number(v).toFixed(d));
const healthColor = (h) => (h >= 85 ? 'var(--green)' : h >= 60 ? 'var(--amber)' : 'var(--red)');
const pct = (p) => `${Math.round(p * 100)}%`;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function formatErr(d) {
  if (!d) return 'Something went wrong.';
  if (typeof d.detail === 'string') return d.detail;
  if (Array.isArray(d.detail)) return d.detail.map((e) => `${(e.loc || []).slice(1).join('.') || 'Input'}: ${e.msg}`).join('. ');
  return 'Something went wrong.';
}

async function api(method, path, body) {
  const res = await fetch('/api' + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(S.token ? { Authorization: 'Bearer ' + S.token } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401 && S.token) {
    logout();
    toast('Your session expired. Log in again.', true);
    throw new Error('Session expired');
  }
  if (!res.ok) throw new Error(formatErr(await res.json().catch(() => null)));
  return res.status === 204 ? null : res.json();
}
const GET = (p) => api('GET', p), POST = (p, b) => api('POST', p, b ?? {}), PUT = (p, b) => api('PUT', p, b),
  PATCH = (p, b) => api('PATCH', p, b), DEL = (p) => api('DELETE', p);

function toast(msg, isErr = false) {
  const el = document.createElement('div');
  el.className = 'toast' + (isErr ? ' error' : '');
  el.textContent = msg;
  $('#toasts').append(el);
  setTimeout(() => el.remove(), isErr ? 6000 : 3200);
}

/* run an action, toast the result, then re-render from the server */
async function act(fn, okMsg) {
  try {
    await fn();
    if (okMsg) toast(okMsg);
    await render(true);
  } catch (e) {
    toast(e.message, true);
  }
}

/* ------------------------------------------------------------------ dialogs */
function fieldHTML(f, val) {
  const id = 'f_' + f.name, v = val ?? f.default ?? '';
  const hint = f.hint ? `<span class="hint">${esc(f.hint)}</span>` : '';
  if (f.type === 'checkbox')
    return `<div class="field"><label class="check"><input type="checkbox" id="${id}" name="${f.name}" ${v ? 'checked' : ''}> ${esc(f.label)}</label>${hint}</div>`;
  let input;
  if (f.type === 'select')
    input = `<select id="${id}" name="${f.name}">${f.options.map(([k, l]) => `<option value="${esc(k)}" ${String(k) === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
  else if (f.type === 'textarea')
    input = `<textarea id="${id}" name="${f.name}" ${f.required ? 'required' : ''} maxlength="${f.max || 1000}">${esc(v)}</textarea>`;
  else if (f.type === 'number')
    input = `<input id="${id}" name="${f.name}" type="number" step="${f.step || 'any'}" ${f.min !== undefined ? `min="${f.min}"` : ''} ${f.max !== undefined ? `max="${f.max}"` : ''} value="${esc(v)}" ${f.required ? 'required' : ''}>`;
  else
    input = `<input id="${id}" name="${f.name}" type="${f.type || 'text'}" value="${esc(v)}" maxlength="${f.max || 120}" ${f.required ? 'required' : ''}>`;
  return `<div class="field"><label for="${id}">${esc(f.label)}</label>${input}${hint}</div>`;
}

function formDialog({ title, fields, values = {}, submit = 'Save', onSubmit }) {
  const d = $('#dlg');
  d.innerHTML = `<form id="dlgForm"><div class="dlg-h"><h3>${esc(title)}</h3><button type="button" class="icon-btn" data-close aria-label="Close"><i class="fa-solid fa-xmark"></i></button></div>
    <div class="dlg-b">${fields.map((f) => fieldHTML(f, values[f.name])).join('')}<div class="form-err hidden" id="dlgErr" role="alert"></div></div>
    <div class="dlg-f"><button type="button" class="btn" data-close>Cancel</button><button class="btn primary" type="submit">${esc(submit)}</button></div></form>`;
  d.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => d.close()));
  $('#dlgForm').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const form = ev.target, vals = {};
    for (const f of fields) {
      const el = form.elements[f.name];
      vals[f.name] = f.type === 'checkbox' ? el.checked : f.type === 'number' ? (el.value === '' ? null : Number(el.value)) : el.value.trim();
    }
    const btn = form.querySelector('[type=submit]'), err = $('#dlgErr');
    btn.disabled = true; err.classList.add('hidden');
    try { await onSubmit(vals); d.close(); }
    catch (e) { err.textContent = e.message; err.classList.remove('hidden'); btn.disabled = false; }
  });
  d.showModal();
  const first = d.querySelector('input,select,textarea'); if (first) first.focus();
}

function confirmDialog(message, label = 'Delete') {
  return new Promise((resolve) => {
    const d = $('#dlg');
    d.innerHTML = `<div class="dlg-h"><h3>Are you sure?</h3></div><div class="dlg-b"><p>${esc(message)}</p></div>
      <div class="dlg-f"><button class="btn" id="cNo">Cancel</button><button class="btn danger" id="cYes">${esc(label)}</button></div>`;
    let result = false;
    $('#cNo').onclick = () => d.close();
    $('#cYes').onclick = () => { result = true; d.close(); };
    d.addEventListener('close', () => resolve(result), { once: true });
    d.showModal();
  });
}

/* ------------------------------------------------------------------ auth */
let authMode = 'login';
function setAuthMode(mode) {
  authMode = mode;
  const signup = mode === 'signup';
  $('#tabLogin').classList.toggle('on', !signup); $('#tabSignup').classList.toggle('on', signup);
  $('#nameField').classList.toggle('hidden', !signup); $('#passHint').classList.toggle('hidden', !signup);
  $('#authTitle').textContent = signup ? 'Create your account' : 'Log in to Nexora';
  $('#authSub').textContent = signup ? 'Set up access for your plant team.' : 'Use the account you created for your plant team.';
  $('#authSubmit').textContent = signup ? 'Create account' : 'Log in';
  $('#aPass').autocomplete = signup ? 'new-password' : 'current-password';
  $('#authErr').classList.add('hidden');
}
$('#tabLogin').onclick = () => setAuthMode('login');
$('#tabSignup').onclick = () => setAuthMode('signup');
$('#authForm').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const err = $('#authErr'), btn = $('#authSubmit');
  const email = $('#aEmail').value.trim(), password = $('#aPass').value, name = $('#aName').value.trim();
  const fail = (m) => { err.textContent = m; err.classList.remove('hidden'); };
  if (!email || !password) return fail('Enter your email and password.');
  if (authMode === 'signup' && name.length < 2) return fail('Enter your full name.');
  btn.disabled = true; err.classList.add('hidden');
  try {
    const out = authMode === 'signup' ? await POST('/auth/signup', { name, email, password }) : await POST('/auth/login', { email, password });
    S.token = out.token; S.user = out.user; localStorage.setItem('nexora_token', out.token);
    $('#aPass').value = '';
    enterApp();
  } catch (e) { fail(e.message); }
  btn.disabled = false;
});

function logout() {
  clearInterval(S.timer); S.token = null; S.user = null;
  localStorage.removeItem('nexora_token');
  $('#app').classList.add('hidden'); $('#auth').classList.remove('hidden');
  setAuthMode('login');
}
$('#logout').onclick = logout;

function enterApp() {
  $('#auth').classList.add('hidden'); $('#app').classList.remove('hidden');
  $('#uName').textContent = S.user.name; $('#uRole').textContent = S.user.role === 'admin' ? 'Admin' : 'Operator';
  $('#uAvatar').textContent = S.user.name.split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
  if (!location.hash) location.hash = '#/overview';
  render();
}

/* ------------------------------------------------------------------ shell & router */
function parseHash() {
  const [r, qs] = location.hash.replace(/^#\/?/, '').split('?');
  return { route: ROUTES.some((x) => x.id === r) ? r : 'overview', params: new URLSearchParams(qs || '') };
}

function drawNav(active, alerts) {
  $('#nav').innerHTML = ROUTES.map((r) => `<a href="#/${r.id}" class="${r.id === active ? 'active' : ''}" ${r.id === active ? 'aria-current="page"' : ''}>
    <i class="fa-solid fa-${r.icon}"></i><span>${r.label}</span>${r.id === 'alerts' && alerts ? `<span class="badge">${alerts}</span>` : ''}</a>`).join('');
}

async function refreshChrome(route) {
  try {
    const [alerts, st, cfg] = await Promise.all([GET('/alerts?status=active'), GET('/ai/status'), GET('/settings')]);
    const crit = alerts.filter((a) => a.severity === 'critical').length;
    drawNav(route, alerts.length);
    $('#bellPip').classList.toggle('hidden', !crit);
    $('#plantName').textContent = cfg.plant_name;
    $('#sysDot').classList.toggle('warn', crit > 0);
    $('#sysText').textContent = crit ? `${crit} critical alert${crit > 1 ? 's' : ''}` : 'All systems operational';
    S.ai = st;
  } catch { /* the view itself will surface API errors */ }
}

async function render(quiet = false) {
  if (!S.token) return;
  clearInterval(S.timer);
  const { route, params } = parseHash();
  const meta = ROUTES.find((r) => r.id === route), ticket = ++S.nav, view = $('#view');
  $('#pageTitle').textContent = meta.title; $('#pageSub').textContent = meta.sub;
  document.title = `${meta.label} | Nexora`;
  drawNav(route, 0);
  if (!quiet) view.innerHTML = '<div class="skeleton"></div>';
  try {
    const html = await VIEWS[route](params);
    if (ticket !== S.nav) return;
    view.innerHTML = html.html; if (html.mount) html.mount(view);
    if (html.poll) S.timer = setInterval(() => render(true), html.poll);
  } catch (e) {
    if (ticket !== S.nav) return;
    view.innerHTML = `<div class="card empty"><b>This page could not load</b>${esc(e.message)}<br><br><button class="btn" id="retry">Try again</button></div>`;
    $('#retry').onclick = () => render();
  }
  refreshChrome(route);
}
window.addEventListener('hashchange', () => { $('#side').classList.remove('open'); render(); });
$('#menuBtn').onclick = () => $('#side').classList.toggle('open');
$('#bell').onclick = () => { S.alertFilter.status = 'active'; location.hash = '#/alerts'; };
$('#searchForm').addEventListener('submit', (e) => { e.preventDefault(); location.hash = '#/assets?q=' + encodeURIComponent($('#q').value.trim()); });
document.addEventListener('keydown', (e) => { if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !$('#dlg').open) { e.preventDefault(); $('#q').focus(); } });

/* ------------------------------------------------------------------ shared pieces */
const SEV_ICON = { critical: ['triangle-exclamation', 'c-red'], high: ['triangle-exclamation', 'c-amber'], medium: ['triangle-exclamation', 'c-yellow'], low: ['bell', 'c-blue'] };
const KIND_ICON = { anomaly: ['atom', 'ic-purple'], optimization: ['leaf', 'ic-green'], predictive: ['clock-rotate-left', 'ic-blue'] };
const ACT_ICON = { work_order: ['file-signature', 'ic-green'], calibration: ['circle-check', 'ic-green'], model: ['brain', 'ic-purple'], sync: ['arrows-rotate', 'ic-blue'], asset: ['cube', 'ic-blue'], alert: ['bell', 'ic-amber'], workflow: ['diagram-project', 'ic-blue'] };
const SRC_LABEL = { gemini: 'Gemma 4', rules: 'Rule-based', manual: 'Manual', seed: 'Demo data' };
const TYPES = ['compressor', 'turbine', 'pump', 'generator', 'reactor', 'fan', 'other'];

function deltaHTML(d, label, goodDown = false) {
  if (d === undefined || d === null) return '';
  const good = goodDown ? d <= 0 : d >= 0;
  return `<span class="${good ? 'c-green' : 'c-red'}"><i class="fa-solid fa-arrow-${d >= 0 ? 'up' : 'down'}" style="font-size:10px"></i> ${Math.abs(d)}%</span> <span class="muted">${label}</span>`;
}

function empty(title, text, btn = '') { return `<div class="empty"><b>${esc(title)}</b>${esc(text)}${btn ? `<div style="margin-top:14px">${btn}</div>` : ''}</div>`; }

/* isometric plant illustration */
function plantSVG() {
  const ox = 210, oy = 78, P = (x, y, z = 0) => [ox + (x - y) * 17.3, oy + (x + y) * 10 - z * 15].map((n) => n.toFixed(1)).join(',');
  const poly = (pts, fill, stroke = 'rgba(130,160,210,.22)') => `<polygon points="${pts.map((p) => P(...p)).join(' ')}" fill="${fill}" stroke="${stroke}" stroke-width=".8"/>`;
  const box = (x, y, w, d, h, c) => ({ k: x + y + (w + d) / 2, svg: poly([[x, y, h], [x + w, y, h], [x + w, y + d, h], [x, y + d, h]], c[0]) + poly([[x, y + d, 0], [x + w, y + d, 0], [x + w, y + d, h], [x, y + d, h]], c[1]) + poly([[x + w, y, 0], [x + w, y + d, 0], [x + w, y + d, h], [x + w, y, h]], c[2]) });
  const cyl = (cx, cy, r, h, c) => { const [bx, by] = P(cx, cy, 0).split(',').map(Number), [, ty] = P(cx, cy, h).split(',').map(Number), rx = 24.5 * r, ry = 14.1 * r;
    return { k: cx + cy, svg: `<path d="M${bx - rx},${ty} L${bx - rx},${by} A${rx},${ry} 0 0 0 ${bx + rx},${by} L${bx + rx},${ty} Z" fill="${c[1]}" stroke="rgba(130,160,210,.22)" stroke-width=".8"/><ellipse cx="${bx}" cy="${ty}" rx="${rx}" ry="${ry}" fill="${c[0]}" stroke="rgba(130,160,210,.3)" stroke-width=".8"/>` }; };
  const body = ['#26354f', '#1a2740', '#1f2e49'], stack = ['#34456a', '#243452'];
  const items = [box(1, 5.2, 4, 3.2, 1.5, body), box(5.8, 5.6, 3, 2.4, 1, body), box(0.8, 1, 2.4, 2.4, 2.4, body), box(3.6, 3.6, 1.6, 1.6, 1.2, body),
    cyl(7.2, 1.8, 0.95, 3.2, stack), cyl(8.7, 3.6, 0.7, 2.3, stack), cyl(5.4, 1.5, 0.8, 4.2, stack), cyl(4.6, 6.2, 0.3, 4.6, stack), cyl(6.1, 6.4, 0.3, 3.8, stack)].sort((a, b) => a.k - b.k);
  const slab = poly([[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]], '#101a2c', 'rgba(59,130,246,.35)') + poly([[0, 10, -.5], [10, 10, -.5], [10, 10, 0], [0, 10, 0]], '#0a111f') + poly([[10, 0, -.5], [10, 10, -.5], [10, 10, 0], [10, 0, 0]], '#0c1424');
  const glow = `<polyline points="${[[0.5, 4.4, 0], [9.6, 4.4, 0]].map((p) => P(...p)).join(' ')}" stroke="rgba(59,130,246,.55)" stroke-width="1.5" fill="none"/>`;
  return `<svg viewBox="0 0 420 250" role="img" aria-label="Isometric plant model">${slab}${glow}${items.map((i) => i.svg).join('')}</svg>`;
}
const RING_SLOTS = [[50, 70], [16, 50], [82, 52], [44, 24]];

/* vibration forecast chart */
function predChart(p) {
  if (!p || !p.actual || !p.actual.length) return empty('No readings yet', 'Send a reading on the Telemetry page to start a trend.');
  const W = 560, H = 250, L = 46, R = 12, T = 12, B = 30, act = p.actual, fc = p.forecast || [];
  const tt = (s) => +new Date(s), t0 = tt(act[0].t), tN = fc.length ? tt(fc[fc.length - 1].t) : tt(act[act.length - 1].t) + 1, now = tt(act[act.length - 1].t);
  const maxV = Math.max(p.threshold, ...act.map((a) => a.v), ...fc.map((f) => f.upper));
  const ymax = Math.max(5, Math.ceil((maxV * 1.08) / 2.5) * 2.5);
  const X = (t) => L + ((tt(t) - t0) / (tN - t0)) * (W - L - R), Y = (v) => T + (1 - v / ymax) * (H - T - B);
  const cur = act[act.length - 1], pt = (t, v) => `${X(t).toFixed(1)},${Y(v).toFixed(1)}`;
  let grid = '';
  for (let v = 0; v <= ymax + 0.01; v += 2.5) grid += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#1d2a40" ${v ? 'stroke-dasharray="3 4"' : ''}/><text x="${L - 8}" y="${Y(v) + 3}" text-anchor="end">${v}</text>`;
  let xl = '';
  for (let i = 0; i <= 6; i++) { const t = t0 + ((tN - t0) * i) / 6; xl += `<text x="${L + ((W - L - R) * i) / 6}" y="${H - 8}" text-anchor="${i === 0 ? 'start' : i === 6 ? 'end' : 'middle'}">${new Date(t).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</text>`; }
  const band = fc.length ? `<polygon points="${[pt(cur.t, cur.v), ...fc.map((f) => pt(f.t, f.upper)), ...[...fc].reverse().map((f) => pt(f.t, f.lower)), pt(cur.t, cur.v)].join(' ')}" fill="rgba(139,108,246,.3)"/>` : '';
  const fline = fc.length ? `<polyline points="${[pt(cur.t, cur.v), ...fc.map((f) => pt(f.t, f.predicted))].join(' ')}" fill="none" stroke="#b39bff" stroke-width="2" stroke-dasharray="5 4"/>` : '';
  const nx = X(cur.t);
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Vibration trend and forecast">${grid}${xl}
    <text transform="translate(11 ${H / 2}) rotate(-90)" text-anchor="middle">Vibration (mm/s)</text>
    <line x1="${L}" x2="${W - R}" y1="${Y(p.threshold)}" y2="${Y(p.threshold)}" stroke="#f0524f" stroke-width="1" stroke-dasharray="2 4"/>
    <text x="${W - R - 2}" y="${Y(p.threshold) - 5}" text-anchor="end" style="fill:#ff8582">Alarm ${p.threshold}</text>
    ${band}<polyline points="${act.map((a) => pt(a.t, a.v)).join(' ')}" fill="none" stroke="#4a8dff" stroke-width="2"/>${fline}
    <line x1="${nx}" x2="${nx}" y1="${T}" y2="${H - B}" stroke="#7a889f" stroke-dasharray="3 3"/><text x="${nx + 5}" y="${T + 9}" style="fill:#cfd8ea">Now</text>
    <circle cx="${nx}" cy="${Y(cur.v)}" r="3.5" fill="#4a8dff" stroke="#0e1625" stroke-width="2"/></svg>`;
}

/* workflow diagram from stored steps */
function stepIcon(s) {
  const l = (s.label + ' ' + s.detail).toLowerCase();
  if (s.kind === 'trigger') return ['bell', 'ic-red']; if (s.kind === 'analysis') return ['brain', 'ic-purple'];
  if (/work order/.test(l)) return ['file-signature', 'ic-blue']; if (/notify|slack|team|mail/.test(l)) return ['comment-dots', 'ic-green'];
  if (/cmms|maximo|sap|record/.test(l)) return ['database', 'ic-amber']; return ['gear', 'ic-blue'];
}
function flowHTML(steps) {
  if (!steps || !steps.length) return '<p class="muted">No steps yet. Edit the workflow to add some.</p>';
  const node = (s) => { const [i, c] = stepIcon(s); return `<div class="node"><div class="ic ${c}"><i class="fa-solid fa-${i}"></i></div><div><b>${esc(s.label)}</b><small>${esc(s.detail)}</small></div></div>`; };
  const pre = steps.filter((s) => s.kind !== 'action'), acts = steps.filter((s) => s.kind === 'action');
  return `<div class="flow">${pre.map(node).join('<i class="fa-solid fa-arrow-right arrow"></i>')}${pre.length && acts.length ? '<i class="fa-solid fa-arrow-right arrow"></i>' : ''}${acts.length ? `<div class="node-col">${acts.map(node).join('')}</div>` : ''}</div>`;
}

/* ================================================================== VIEWS */
const VIEWS = {};

/* ---------- overview ---------- */
VIEWS.overview = async () => {
  const [o, assets] = await Promise.all([GET('/overview'), GET('/assets')]);
  const sel = assets.some((a) => a.id === S.predAsset) ? S.predAsset : o.top_risk_asset_id;
  const pred = sel ? await GET(`/assets/${sel}/prediction`) : null;
  const k = o.kpis, hs = o.health, sm = o.alert_summary;
  const kpi = (lbl, val, sub, ic, cls, extra = '') => `<div class="card kpi"><div><div class="lbl">${lbl}</div><div class="val">${val}</div><div class="sub">${sub}</div></div>${extra || `<div class="kpi-ic ${cls}"><i class="fa-solid fa-${ic}"></i></div>`}</div>`;
  const oee = k.oee ? k.oee.value : 0;
  const rings = o.map_assets.map((a, i) => `<button class="ring ${a.status}" style="left:${RING_SLOTS[i][0]}%;top:${RING_SLOTS[i][1]}%;--p:${a.health};--c:${healthColor(a.health)}" data-asset="${a.id}" aria-label="${esc(a.tag)} health ${a.health} percent" title="${esc(a.name)}: ${a.health}%"><span>${a.health}</span></button>`).join('');
  const risk = pred && pred.failure_probability_72h !== undefined ? pred.failure_probability_72h : 0;
  const high = risk >= 0.6;
  const html = `
  <div class="range-row"><span class="pill"><i class="fa-regular fa-calendar"></i> Last 24 hours</span></div>
  <section class="kpis">
    ${kpi('Assets monitored', k.assets.toLocaleString(), `<span class="c-green">${hs.healthy}</span> <span class="muted">healthy</span>`, 'cube', 'ic-blue')}
    ${kpi('Current alerts', k.alerts, `<span class="c-red"><i class="fa-solid fa-arrow-up" style="font-size:10px"></i> ${k.critical_alerts} critical</span>`, 'bell', 'ic-red')}
    ${kpi('MTBF', `${k.mtbf ? k.mtbf.value : '-'}<small>days</small>`, k.mtbf ? deltaHTML(k.mtbf.delta, 'vs last 30 days') : '', 'heart-pulse', 'ic-purple')}
    ${kpi('OEE', `${oee}%`, k.oee ? deltaHTML(k.oee.delta, 'vs last 30 days') : '', '', '', `<div class="oee-ring" style="background:conic-gradient(var(--green) ${oee}%, rgba(255,255,255,.1) 0)"></div>`)}
    ${kpi('Energy consumption', `${k.energy ? k.energy.value : '-'}<small>MWh</small>`, k.energy ? deltaHTML(k.energy.delta, 'vs yesterday', true) : '', 'bolt', 'ic-amber')}
  </section>
  <div class="dash">
    <div class="dash-left">
      <section class="card s-health"><div class="card-h"><h2>Asset health overview</h2></div>
        <div class="plant">${plantSVG()}${rings}</div>
        <div class="health-foot"><button class="link blue" data-go="assets">View all assets <i class="fa-solid fa-arrow-right"></i></button>
          <span class="muted" style="font-size:11.5px">Lowest 4 by health</span></div></section>
      <section class="card s-summary"><div class="card-h"><h2>Alert summary</h2><button class="link" data-go="alerts">View all</button></div>
        ${['critical', 'high', 'medium', 'low'].map((s) => `<div class="row-sum"><i class="fa-solid fa-${SEV_ICON[s][0]} sev-ic ${SEV_ICON[s][1]}"></i><span>${cap(s)}</span><span class="n ${SEV_ICON[s][1]}">${sm[s]}</span></div>`).join('')}
        <div class="total-row"><span>Total</span><b>${sm.total}</b></div></section>
      <section class="card s-recent"><div class="card-h"><h2>Recent alerts</h2></div>
        ${o.recent_alerts.length ? o.recent_alerts.map((a) => `<div class="alert-mini"><i class="fa-solid fa-${SEV_ICON[a.severity][0]} ${SEV_ICON[a.severity][1]}"></i><div><div class="t"><span class="tag ${a.severity}">${cap(a.severity)}</span>${esc(a.title)}</div><div class="s">${esc(a.asset_tag || 'No asset')} &bull; ${ago(a.created_at)}</div></div></div>`).join('') : empty('No active alerts', 'Everything is quiet.')}
        <button class="link blue" data-go="alerts" style="margin-top:8px">View all alerts <i class="fa-solid fa-arrow-right"></i></button></section>
      <section class="card s-pred"><div class="card-h"><h2>Predictive analytics</h2>
        <label class="sr" for="predSel">Asset</label><select id="predSel" style="width:auto;min-width:150px;padding:5px 28px 5px 10px">${assets.map((a) => `<option value="${a.id}" ${a.id === sel ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}</select></div>
        <div class="legend"><span><i style="background:#4a8dff"></i>Actual</span><span><i class="dash-l"></i>Predicted</span><span><i class="band"></i>Confidence interval</span></div>
        <div class="chart">${predChart(pred)}</div>
        ${pred && pred.actual ? `<div class="warn-bar ${high ? '' : 'ok'}"><i class="fa-solid fa-${high ? 'triangle-exclamation c-red' : 'circle-check c-green'}"></i>
          <span class="grow">${high ? 'High probability of reaching the alarm level within 72 hours' : 'Low risk of reaching the alarm level within 72 hours'}</span>
          <span class="muted">Probability: <b style="color:var(--text)">${pct(risk)}</b></span><button class="link blue" data-go="analytics">View analysis <i class="fa-solid fa-arrow-right"></i></button></div>` : ''}</section>
      <section class="card s-flow"><div class="card-h"><h2>Workflow automation</h2><button class="link" data-go="workflows">View all workflows <i class="fa-solid fa-arrow-right"></i></button></div>
        ${o.workflow ? `<p class="muted" style="margin-bottom:6px">${esc(o.workflow.name)}</p>${flowHTML(o.workflow.steps)}` : empty('No active workflow', 'Create one to define your escalation steps.')}</section>
    </div>
    <div class="dash-right">
      <section class="card"><div class="card-h"><h2>AI insights</h2><button class="link" data-go="insights">View all</button></div>
        ${o.insights.length ? o.insights.map((i) => { const [ic, c] = KIND_ICON[i.kind]; return `<div class="ins"><div class="ic ${c}"><i class="fa-solid fa-${ic}"></i></div><div><div class="top"><b>${esc(i.title)}</b><span class="faint" style="white-space:nowrap;font-size:11.5px">${ago(i.created_at)}</span></div><p>${esc(i.body)}</p><button class="btn sm" data-go="insights">View insight</button></div></div>`; }).join('') : empty('No insights waiting', 'Generate some from the AI Insights page.')}</section>
      <section class="card"><div class="card-h"><h2>System activity</h2></div>
        ${o.activity.map((a) => { const [ic, c] = ACT_ICON[a.kind] || ['circle', 'ic-blue']; return `<div class="act"><div class="ic ${c}"><i class="fa-solid fa-${ic}"></i></div><div>${esc(a.text)}<small>${esc(a.detail)}</small></div><time>${ago(a.created_at)}</time></div>`; }).join('') || empty('No activity yet', '')}</section>
    </div>
  </div>`;
  return { html, poll: 20000, mount: (v) => {
    v.querySelectorAll('[data-go]').forEach((b) => (b.onclick = () => (location.hash = '#/' + b.dataset.go)));
    v.querySelectorAll('.ring').forEach((b) => (b.onclick = () => (location.hash = '#/telemetry?asset=' + b.dataset.asset)));
    const sel2 = $('#predSel', v); if (sel2) sel2.onchange = () => { S.predAsset = Number(sel2.value); render(true); };
  } };
};

/* ---------- assets ---------- */
const assetFields = (edit) => [
  { name: 'tag', label: 'Tag', required: true, max: 30, hint: 'Letters, numbers, dash. Example: C-205' },
  { name: 'name', label: 'Name', required: true, max: 80 },
  { name: 'type', label: 'Type', type: 'select', options: TYPES.map((t) => [t, cap(t)]) },
  { name: 'location', label: 'Location', max: 80 }, { name: 'serial', label: 'Serial number', max: 60 },
  { name: 'vibration', label: 'Vibration (mm/s)', type: 'number', step: 0.1, min: 0, required: true },
  { name: 'temperature', label: 'Temperature (\u00b0C)', type: 'number', step: 0.1, required: true },
  { name: 'pressure', label: 'Pressure (bar), optional', type: 'number', step: 0.1, min: 0 },
  { name: 'flow_rate', label: 'Flow rate (L/min), optional', type: 'number', step: 1, min: 0 },
];
function openAssetForm(a) {
  if (!a) return formDialog({ title: 'Register asset', fields: assetFields(), values: { type: 'pump', vibration: 1, temperature: 40 }, submit: 'Register asset',
    onSubmit: async (v) => { await POST('/assets', v); toast('Asset registered'); render(true); } });
  formDialog({ title: `Edit ${a.tag}`, fields: assetFields(true), values: a, submit: 'Save changes', onSubmit: async (v) => {
    const diff = {}; for (const k of Object.keys(v)) if ((v[k] ?? null) !== (a[k] ?? null) && !(v[k] === '' && !a[k])) diff[k] = v[k];
    if (!Object.keys(diff).length) return;
    await PATCH('/assets/' + a.id, diff); toast('Asset updated'); render(true); } });
}

VIEWS.assets = async (params) => {
  const q = params.get('q') || '', type = params.get('type') || '', status = params.get('status') || '';
  const list = await GET(`/assets?q=${encodeURIComponent(q)}&type=${type}&status=${status}`);
  const html = `<div class="card"><div class="toolbar">
      <div class="grow"><label class="sr" for="aq">Filter assets</label><input id="aq" type="text" placeholder="Filter by tag, name or location" value="${esc(q)}"></div>
      <label class="sr" for="atype">Type</label><select id="atype"><option value="">All types</option>${TYPES.map((t) => `<option value="${t}" ${t === type ? 'selected' : ''}>${cap(t)}</option>`).join('')}</select>
      <label class="sr" for="astat">Status</label><select id="astat"><option value="">All statuses</option>${['healthy', 'warning', 'critical'].map((t) => `<option value="${t}" ${t === status ? 'selected' : ''}>${cap(t)}</option>`).join('')}</select>
      <button class="btn primary" id="addAsset"><i class="fa-solid fa-plus"></i> Register asset</button></div>
    ${list.length ? `<div class="table-wrap"><table><thead><tr><th>Asset</th><th>Type</th><th>Location</th><th>Health</th><th>Vibration</th><th>Temp</th><th>Status</th><th></th></tr></thead><tbody>
    ${list.map((a) => `<tr><td><b>${esc(a.tag)}</b><div class="muted">${esc(a.name)}</div></td><td>${cap(esc(a.type))}</td><td>${esc(a.location) || '-'}</td>
      <td><span class="bar"><i style="width:${a.health}%;background:${healthColor(a.health)}"></i></span><span class="mono">${a.health}%</span></td>
      <td class="mono">${num(a.vibration)} mm/s</td><td class="mono">${num(a.temperature)} \u00b0C</td><td><span class="chip ${a.status}">${cap(a.status)}</span></td>
      <td class="actions"><button class="btn sm" data-ins="${a.id}">Inspect</button><button class="btn sm" data-edit="${a.id}">Edit</button><button class="btn sm danger" data-del="${a.id}" aria-label="Delete ${esc(a.tag)}"><i class="fa-solid fa-trash"></i></button></td></tr>`).join('')}
    </tbody></table></div>` : empty('No assets match', q || type || status ? 'Clear the filters to see everything.' : 'Register your first asset to start monitoring.', '<button class="btn primary" id="addAsset2">Register asset</button>')}</div>`;
  return { html, mount: (v) => {
    const go = () => { const p = new URLSearchParams(); const f = [['q', $('#aq', v).value.trim()], ['type', $('#atype', v).value], ['status', $('#astat', v).value]]; f.forEach(([k, x]) => x && p.set(k, x)); location.hash = '#/assets' + (p.toString() ? '?' + p : ''); };
    let t; $('#aq', v).oninput = () => { clearTimeout(t); t = setTimeout(go, 350); };
    $('#atype', v).onchange = go; $('#astat', v).onchange = go;
    v.querySelectorAll('#addAsset,#addAsset2').forEach((b) => (b.onclick = () => openAssetForm()));
    v.querySelectorAll('[data-ins]').forEach((b) => (b.onclick = () => (location.hash = '#/telemetry?asset=' + b.dataset.ins)));
    v.querySelectorAll('[data-edit]').forEach((b) => (b.onclick = () => openAssetForm(list.find((a) => a.id == b.dataset.edit))));
    v.querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => { const a = list.find((x) => x.id == b.dataset.del);
      if (await confirmDialog(`Delete ${a.tag} and all of its readings and alerts? This cannot be undone.`)) act(() => DEL('/assets/' + a.id), 'Asset deleted'); }));
  } };
};

/* ---------- telemetry ---------- */
VIEWS.telemetry = async (params) => {
  const assets = await GET('/assets?');
  if (!assets.length) return { html: `<div class="card">${empty('No assets yet', 'Register an asset first.', '<a class="btn primary" href="#/assets">Go to assets</a>')}</div>` };
  const id = assets.some((a) => a.id == params.get('asset')) ? Number(params.get('asset')) : (assets.some((a) => a.id === S.telAsset) ? S.telAsset : assets[0].id);
  S.telAsset = id;
  const [a, readings, pred] = await Promise.all([GET('/assets/' + id), GET(`/assets/${id}/readings?limit=48`), GET(`/assets/${id}/prediction`)]);
  const tile = (l, v, u, c = '') => `<div class="card stat"><span class="muted">${l}</span><div class="big mono ${c}">${v}<small class="muted" style="font-size:12px"> ${u}</small></div></div>`;
  const vals = readings.map((r) => r.vibration), ymax = Math.max(pred.threshold * 1.15, ...vals, 1);
  const sx = (i) => 30 + (i / Math.max(vals.length - 1, 1)) * 520, sy = (v) => 10 + (1 - v / ymax) * 100;
  const spark = `<svg viewBox="0 0 560 130" role="img" aria-label="Recent vibration readings"><line x1="30" x2="550" y1="${sy(pred.threshold)}" y2="${sy(pred.threshold)}" stroke="#f0524f" stroke-dasharray="2 4"/><text x="548" y="${sy(pred.threshold) - 4}" text-anchor="end" style="fill:#ff8582">Alarm ${pred.threshold}</text>
    <text x="24" y="${sy(0) + 3}" text-anchor="end">0</text><text x="24" y="${sy(ymax) + 8}" text-anchor="end">${ymax.toFixed(1)}</text>
    <polyline fill="none" stroke="#4a8dff" stroke-width="2" points="${vals.map((v, i) => `${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join(' ')}"/></svg>`;
  const html = `<div class="toolbar"><label class="sr" for="telSel">Asset</label><select id="telSel" style="min-width:220px">${assets.map((x) => `<option value="${x.id}" ${x.id === id ? 'selected' : ''}>${esc(x.tag)} - ${esc(x.name)}</option>`).join('')}</select>
      <span class="chip healthy">Live &middot; refreshes every 6 s</span><span class="grow"></span>
      <button class="btn ai" id="simBtn"><i class="fa-solid fa-dice"></i> Simulate reading</button><button class="btn primary" id="sendBtn"><i class="fa-solid fa-paper-plane"></i> Send reading</button></div>
    <div class="grid-4" style="margin-bottom:12px">${tile('Vibration', num(a.vibration), 'mm/s', a.vibration >= pred.threshold ? 'c-red' : '')}${tile('Temperature', num(a.temperature), '\u00b0C')}${tile('Pressure', a.pressure === null ? '-' : num(a.pressure), 'bar')}
      ${tile('Health', a.health + '%', a.status, a.status === 'healthy' ? 'c-green' : a.status === 'warning' ? 'c-amber' : 'c-red')}</div>
    <div class="grid-2"><section class="card"><div class="card-h"><h3>Vibration, last ${vals.length} readings</h3></div><div class="spark">${spark}</div></section>
      <section class="card"><div class="card-h"><h3>Latest readings</h3></div><div class="table-wrap"><table><thead><tr><th>Time</th><th>Vibration</th><th>Temp</th></tr></thead><tbody>
      ${[...readings].reverse().slice(0, 8).map((r) => `<tr><td>${new Date(r.ts).toLocaleTimeString()}</td><td class="mono">${num(r.vibration, 2)} mm/s</td><td class="mono">${num(r.temperature)} \u00b0C</td></tr>`).join('')}</tbody></table></div></section></div>`;
  return { html, poll: 6000, mount: (v) => {
    $('#telSel', v).onchange = (e) => (location.hash = '#/telemetry?asset=' + e.target.value);
    $('#sendBtn', v).onclick = () => formDialog({ title: `Send reading for ${a.tag}`, submit: 'Send reading', values: { vibration: a.vibration, temperature: a.temperature, pressure: a.pressure, flow_rate: a.flow_rate },
      fields: [{ name: 'vibration', label: 'Vibration (mm/s)', type: 'number', step: 0.1, min: 0, required: true }, { name: 'temperature', label: 'Temperature (\u00b0C)', type: 'number', step: 0.1, required: true },
        { name: 'pressure', label: 'Pressure (bar), optional', type: 'number', step: 0.1, min: 0 }, { name: 'flow_rate', label: 'Flow rate (L/min), optional', type: 'number', min: 0 }],
      onSubmit: async (val) => { const r = await POST(`/assets/${a.id}/readings`, val); toast(r.created_alerts.length ? 'Reading saved. A new alert was raised.' : 'Reading saved'); render(true); } });
    $('#simBtn', v).onclick = () => act(async () => {
      const j = (x, p) => Math.max(0, +(x * (1 + (Math.random() - 0.35) * p)).toFixed(2));
      await POST(`/assets/${a.id}/readings`, { vibration: j(a.vibration, 0.25), temperature: j(a.temperature, 0.06), pressure: a.pressure, flow_rate: a.flow_rate }); }, 'Simulated reading saved');
  } };
};

/* ---------- alerts ---------- */
function aiBox(a) {
  const r = a.ai_analysis; if (!r) return '';
  const d = r.analysis, byAI = r.source === 'gemini';
  const urg = { immediate: 'Act now', within_24h: 'Within 24 hours', this_week: 'This week', monitor: 'Keep monitoring' }[d.urgency];
  const review = a.ai_review === 'pending'
    ? `<div class="ai-review"><b>Needs human review.</b><span class="muted">Nothing is created until you approve.</span><button class="btn sm good" data-review="approve" data-id="${a.id}">Approve and draft work order</button><button class="btn sm" data-review="reject" data-id="${a.id}">Reject</button></div>`
    : `<div class="ai-review"><span class="chip ${a.ai_review}">${cap(a.ai_review)} by a person</span></div>`;
  return `<div class="ai-box"><h4><i class="fa-solid fa-microchip"></i> ${byAI ? `AI diagnosis &middot; Gemma 4 (${esc(r.model)})` : 'Rule-based diagnosis'}
    ${!byAI && r.error && r.error !== 'no_api_key' ? '<span class="chip warning">AI unavailable, fallback used</span>' : ''}</h4>
    <div><b>${esc(d.failure_mode)}.</b> ${esc(d.probable_cause)}</div>
    <div class="meta"><span>Urgency: <b style="color:var(--text)">${urg}</b></span><span>Confidence: <b style="color:var(--text)">${pct(d.confidence)}</b></span></div>
    <ul>${d.recommended_actions.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
    ${d.uncertainty_notes ? `<p class="muted" style="margin-top:8px;font-size:12px">${esc(d.uncertainty_notes)}</p>` : ''}${review}</div>`;
}

async function openAlertForm(a) {
  const assets = await GET('/assets');
  formDialog({ title: a ? 'Edit alert' : 'New alert', submit: a ? 'Save changes' : 'Create alert',
    values: a ? { ...a, asset_id: a.asset_id ?? '' } : { severity: 'medium', status: 'open', asset_id: '' },
    fields: [{ name: 'title', label: 'Title', required: true, max: 120 }, { name: 'asset_id', label: 'Asset', type: 'select', options: [['', 'No asset'], ...assets.map((x) => [x.id, `${x.tag} - ${x.name}`])] },
      { name: 'severity', label: 'Severity', type: 'select', options: ['critical', 'high', 'medium', 'low'].map((s) => [s, cap(s)]) },
      { name: 'status', label: 'Status', type: 'select', options: ['open', 'acknowledged', 'resolved'].map((s) => [s, cap(s)]) },
      { name: 'description', label: 'Description', type: 'textarea', max: 1000 }],
    onSubmit: async (v) => { const body = { ...v, asset_id: v.asset_id === '' ? null : Number(v.asset_id) };
      if (a) await PUT('/alerts/' + a.id, body); else await POST('/alerts', body);
      toast(a ? 'Alert updated' : 'Alert created'); render(true); } });
}

VIEWS.alerts = async () => {
  const f = S.alertFilter, list = await GET(`/alerts?status=${f.status}&severity=${f.severity}`);
  const html = `<div class="toolbar"><label class="sr" for="fStat">Status</label><select id="fStat">${[['active', 'Active'], ['open', 'Open'], ['acknowledged', 'Acknowledged'], ['resolved', 'Resolved'], ['', 'All']].map(([k, l]) => `<option value="${k}" ${k === f.status ? 'selected' : ''}>${l}</option>`).join('')}</select>
      <label class="sr" for="fSev">Severity</label><select id="fSev"><option value="">All severities</option>${['critical', 'high', 'medium', 'low'].map((s) => `<option value="${s}" ${s === f.severity ? 'selected' : ''}>${cap(s)}</option>`).join('')}</select>
      <span class="grow"></span><button class="btn primary" id="newAlert"><i class="fa-solid fa-plus"></i> New alert</button></div>
    ${list.length ? list.map((a) => `<article class="item ${a.status === 'resolved' ? 'resolved' : a.severity}">
      <div class="item-h"><div><span class="tag ${a.severity}">${cap(a.severity)}</span><b>${esc(a.title)}</b><div class="muted" style="margin-top:4px">${esc(a.asset_tag || 'No asset')} &bull; ${ago(a.created_at)} &bull; ${a.source === 'rule' ? 'Raised by threshold rule' : 'Created manually'}</div></div><span class="chip ${a.status}">${cap(a.status)}</span></div>
      ${a.description ? `<p class="muted" style="margin-top:8px">${esc(a.description)}</p>` : ''}${aiBox(a)}
      <div class="item-actions">
        ${a.status === 'open' ? `<button class="btn sm" data-st="acknowledged" data-id="${a.id}">Acknowledge</button>` : ''}
        ${a.status !== 'resolved' ? `<button class="btn sm good" data-st="resolved" data-id="${a.id}">Resolve</button>` : `<button class="btn sm" data-st="open" data-id="${a.id}">Reopen</button>`}
        ${a.asset_id ? `<button class="btn sm ai" data-ai="${a.id}"><i class="fa-solid fa-microchip"></i> ${a.ai_analysis ? 'Re-run AI analysis' : 'Analyze with AI'}</button>` : ''}
        <button class="btn sm" data-edit="${a.id}">Edit</button><button class="btn sm danger" data-del="${a.id}" aria-label="Delete alert"><i class="fa-solid fa-trash"></i></button></div></article>`).join('')
      : `<div class="card">${empty('No alerts here', 'Nothing matches these filters.')}</div>`}`;
  return { html, mount: (v) => {
    $('#fStat', v).onchange = (e) => { f.status = e.target.value; render(); };
    $('#fSev', v).onchange = (e) => { f.severity = e.target.value; render(); };
    $('#newAlert', v).onclick = () => openAlertForm();
    v.querySelectorAll('[data-st]').forEach((b) => (b.onclick = () => act(() => PATCH('/alerts/' + b.dataset.id, { status: b.dataset.st }), 'Alert ' + b.dataset.st)));
    v.querySelectorAll('[data-ai]').forEach((b) => (b.onclick = () => { b.disabled = true; b.textContent = 'Analyzing...'; act(() => POST(`/alerts/${b.dataset.ai}/analyze`), 'Analysis ready for review'); }));
    v.querySelectorAll('[data-review]').forEach((b) => (b.onclick = () => act(() => POST(`/alerts/${b.dataset.id}/analysis/review`, { decision: b.dataset.review }), b.dataset.review === 'approve' ? 'Work order drafted' : 'AI suggestion rejected')));
    v.querySelectorAll('[data-edit]').forEach((b) => (b.onclick = () => openAlertForm(list.find((a) => a.id == b.dataset.edit))));
    v.querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => { if (await confirmDialog('Delete this alert?')) act(() => DEL('/alerts/' + b.dataset.del), 'Alert deleted'); }));
  } };
};

/* ---------- workflows ---------- */
const stepsToText = (s) => (s || []).map((x) => `${x.kind} | ${x.label} | ${x.detail}`).join('\n');
function textToSteps(t) {
  return t.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
    const [kind, label, ...rest] = l.split('|').map((x) => x.trim());
    if (!['trigger', 'analysis', 'action'].includes(kind)) throw new Error(`Each line must start with trigger, analysis or action. Problem line: "${l}"`);
    return { kind, label: label || cap(kind), detail: rest.join(' | ') };
  });
}
function openWorkflowForm(w) {
  formDialog({ title: w ? 'Edit workflow' : 'New workflow', submit: w ? 'Save changes' : 'Create workflow',
    values: w ? { ...w, steps: stepsToText(w.steps) } : { enabled: true, steps: 'trigger | Alert Trigger | Vibration anomaly\nanalysis | AI Analysis | Gemma 4 diagnosis\naction | Create Work Order | After approval' },
    fields: [{ name: 'name', label: 'Name', required: true, max: 120 }, { name: 'description', label: 'Description', type: 'textarea', max: 600 },
      { name: 'steps', label: 'Steps', type: 'textarea', max: 1500, hint: 'One per line: kind | label | detail. Kinds: trigger, analysis, action.' }, { name: 'enabled', label: 'Enabled', type: 'checkbox' }],
    onSubmit: async (v) => { const body = { name: v.name, description: v.description, enabled: v.enabled, steps: textToSteps(v.steps) };
      if (w) await PUT('/workflows/' + w.id, body); else await POST('/workflows', body);
      toast(w ? 'Workflow updated' : 'Workflow created'); render(true); } });
}
VIEWS.workflows = async () => {
  const list = await GET('/workflows');
  const html = `<div class="note">Workflows describe who does what after an alert. Running one records the run in the activity log. It does not call external systems in this build.</div>
    <div class="toolbar"><span class="grow"></span><button class="btn primary" id="newWf"><i class="fa-solid fa-plus"></i> New workflow</button></div>
    ${list.length ? list.map((w) => `<section class="card" style="margin-bottom:12px"><div class="card-h"><h3 style="text-transform:none;font-size:14px;letter-spacing:0">${esc(w.name)}</h3><span class="chip ${w.enabled ? 'connected' : 'disconnected'}">${w.enabled ? 'Enabled' : 'Paused'}</span></div>
      ${w.description ? `<p class="muted" style="margin-bottom:8px">${esc(w.description)}</p>` : ''}${flowHTML(w.steps)}
      <div class="item-actions" style="align-items:center"><span class="muted">Run ${w.run_count} time${w.run_count === 1 ? '' : 's'}${w.last_run ? ` &bull; last ${ago(w.last_run)}` : ''}</span><span class="grow" style="flex:1"></span>
      <button class="btn sm" data-toggle="${w.id}" data-on="${w.enabled}">${w.enabled ? 'Pause' : 'Enable'}</button><button class="btn sm good" data-run="${w.id}" ${w.enabled ? '' : 'disabled'}>Run now</button>
      <button class="btn sm" data-edit="${w.id}">Edit</button><button class="btn sm danger" data-del="${w.id}" aria-label="Delete workflow"><i class="fa-solid fa-trash"></i></button></div></section>`).join('')
      : `<div class="card">${empty('No workflows yet', 'Create one to document your escalation path.')}</div>`}`;
  return { html, mount: (v) => {
    $('#newWf', v).onclick = () => openWorkflowForm();
    v.querySelectorAll('[data-toggle]').forEach((b) => (b.onclick = () => act(() => PATCH('/workflows/' + b.dataset.toggle, { enabled: b.dataset.on !== 'true' }), 'Workflow updated')));
    v.querySelectorAll('[data-run]').forEach((b) => (b.onclick = () => act(() => POST(`/workflows/${b.dataset.run}/run`), 'Workflow run recorded')));
    v.querySelectorAll('[data-edit]').forEach((b) => (b.onclick = () => openWorkflowForm(list.find((w) => w.id == b.dataset.edit))));
    v.querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => { if (await confirmDialog('Delete this workflow?')) act(() => DEL('/workflows/' + b.dataset.del), 'Workflow deleted'); }));
  } };
};

/* ---------- analytics ---------- */
VIEWS.analytics = async () => {
  const d = await GET('/analytics/fleet'), total = d.counts.healthy + d.counts.warning + d.counts.critical || 1;
  const html = `<div class="grid-4" style="margin-bottom:12px">
      <div class="card stat"><span class="muted">Average health</span><div class="big">${d.avg_health}%</div></div>
      <div class="card stat"><span class="muted">Healthy</span><div class="big c-green">${d.counts.healthy}</div></div>
      <div class="card stat"><span class="muted">Warning</span><div class="big c-amber">${d.counts.warning}</div></div>
      <div class="card stat"><span class="muted">Critical</span><div class="big c-red">${d.counts.critical}</div></div></div>
    <div class="grid-2"><section class="card"><div class="card-h"><h3>Health by equipment type</h3></div>
      ${d.by_type.map((t) => `<div class="hbar"><div class="r"><span>${cap(esc(t.type))} <span class="muted">(${t.count})</span></span><b style="color:${healthColor(t.avg_health)}">${t.avg_health}%</b></div><div class="t"><i style="width:${t.avg_health}%;background:${healthColor(t.avg_health)}"></i></div></div>`).join('') || empty('No data', '')}
      <p class="muted" style="font-size:12px;margin-top:10px">Share of fleet: ${pct(d.counts.healthy / total)} healthy, ${pct(d.counts.warning / total)} warning, ${pct(d.counts.critical / total)} critical.</p></section>
      <section class="card"><div class="card-h"><h3>Highest failure risk, next 72 hours</h3></div><div class="table-wrap"><table><thead><tr><th>Asset</th><th>Risk</th><th>Trend</th><th>To alarm</th></tr></thead><tbody>
      ${d.risk.map((r) => `<tr><td><b>${esc(r.tag)}</b></td><td><span class="bar"><i style="width:${r.failure_probability_72h * 100}%;background:${r.failure_probability_72h >= 0.6 ? 'var(--red)' : r.failure_probability_72h >= 0.3 ? 'var(--amber)' : 'var(--green)'}"></i></span><span class="mono">${pct(r.failure_probability_72h)}</span></td>
      <td class="mono">${r.slope_per_hour > 0 ? '+' : ''}${r.slope_per_hour}/h</td><td class="mono">${r.hours_to_threshold === null ? '-' : r.hours_to_threshold === 0 ? 'Over' : r.hours_to_threshold + ' h'}</td></tr>`).join('')}</tbody></table></div>
      <p class="muted" style="font-size:12px;margin-top:10px">Straight-line trend of recent vibration readings against the alarm level (${d.vibration_alarm} mm/s). No AI model is used here.</p></section></div>`;
  return { html };
};

/* ---------- AI insights ---------- */
VIEWS.insights = async () => {
  const [list, st] = await Promise.all([GET('/insights'), GET('/ai/status')]);
  const html = `<div class="note"><b>Where AI is used:</b> asset and alert diagnosis. Thresholds, health scores and forecasts are ordinary calculations. Every AI output below is a suggestion that a person approves or dismisses.
      <br><span class="muted">${st.configured ? `Connected to the Gemini API with ${esc(st.model)}.` : 'No Gemini API key is set, so diagnoses use the built-in rule-based fallback.'} Only the asset tag and sensor numbers are sent.</span></div>
    <div class="toolbar"><span class="grow"></span><button class="btn" id="newIns"><i class="fa-solid fa-plus"></i> Add insight</button><button class="btn ai" id="genIns"><i class="fa-solid fa-microchip"></i> Generate insights</button></div>
    ${list.length ? list.map((i) => { const [ic, c] = KIND_ICON[i.kind]; return `<article class="item ${i.status === 'dismissed' ? 'resolved' : ''}" style="border-left-color:var(--purple)"><div class="ins" style="border:0;padding:0"><div class="ic ${c}"><i class="fa-solid fa-${ic}"></i></div><div>
      <div class="item-h"><b>${esc(i.title)}</b><span><span class="chip ${i.status}">${cap(i.status)}</span></span></div>
      <p style="color:#c3cde0;font-size:13px;margin:6px 0">${esc(i.body)}</p>
      <div class="muted" style="font-size:12px">${i.asset_tag ? esc(i.asset_tag) + ' &bull; ' : ''}Source: ${SRC_LABEL[i.source] || esc(i.source)}${i.confidence !== null ? ` &bull; Confidence ${pct(i.confidence)}` : ''} &bull; ${ago(i.created_at)}</div>
      <div class="item-actions">${i.status !== 'approved' ? `<button class="btn sm good" data-st="approved" data-id="${i.id}">Approve</button>` : ''}${i.status !== 'dismissed' ? `<button class="btn sm" data-st="dismissed" data-id="${i.id}">Dismiss</button>` : `<button class="btn sm" data-st="pending" data-id="${i.id}">Restore</button>`}
      <button class="btn sm danger" data-del="${i.id}" aria-label="Delete insight"><i class="fa-solid fa-trash"></i></button></div></div></div></article>`; }).join('')
      : `<div class="card">${empty('No insights yet', 'Generate insights to diagnose the assets with the highest risk.')}</div>`}`;
  return { html, mount: (v) => {
    $('#genIns', v).onclick = (e) => { e.currentTarget.disabled = true; e.currentTarget.textContent = 'Generating...';
      act(async () => { const r = await POST('/insights/generate'); toast(r.created.length ? `${r.created.length} insight(s) ready for review` : (r.skipped_existing ? 'Risky assets already have insights waiting for review' : 'No assets need a new diagnosis right now')); }); };
    $('#newIns', v).onclick = async () => { const assets = await GET('/assets');
      formDialog({ title: 'Add insight', submit: 'Add insight', values: { kind: 'optimization', asset_id: '' },
        fields: [{ name: 'title', label: 'Title', required: true, max: 140 }, { name: 'kind', label: 'Type', type: 'select', options: [['anomaly', 'Anomaly'], ['optimization', 'Optimization'], ['predictive', 'Predictive maintenance']] },
          { name: 'asset_id', label: 'Asset', type: 'select', options: [['', 'No asset'], ...assets.map((a) => [a.id, a.tag])] }, { name: 'body', label: 'Details', type: 'textarea', max: 1500 }],
        onSubmit: async (val) => { await POST('/insights', { ...val, asset_id: val.asset_id === '' ? null : Number(val.asset_id) }); toast('Insight added'); render(true); } }); };
    v.querySelectorAll('[data-st]').forEach((b) => (b.onclick = () => act(() => PATCH('/insights/' + b.dataset.id, { status: b.dataset.st }), 'Insight ' + b.dataset.st)));
    v.querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => { if (await confirmDialog('Delete this insight?')) act(() => DEL('/insights/' + b.dataset.del), 'Insight deleted'); }));
  } };
};

/* ---------- reports ---------- */
function csvCell(x) { let s = x === null || x === undefined ? '' : String(x); if (/^[=+\-@]/.test(s)) s = "'" + s; return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }
function download(name, text, type) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); }
const toCSV = (rows, cols) => [cols.join(','), ...rows.map((r) => cols.map((c) => csvCell(r[c])).join(','))].join('\n');
VIEWS.reports = async () => {
  const s = await GET('/reports/summary');
  const html = `<div class="grid-3" style="margin-bottom:12px">
      <div class="card stat"><span class="muted">Assets</span><div class="big">${s.assets.total}</div><div class="muted">${s.assets.critical} critical, ${s.assets.warning} warning</div></div>
      <div class="card stat"><span class="muted">Alerts</span><div class="big">${s.alerts.total}</div><div class="muted">${s.alerts.open} open, ${s.alerts.resolved} resolved, ${s.alerts.raised_last_24h} in the last 24 h</div></div>
      <div class="card stat"><span class="muted">AI suggestions reviewed</span><div class="big">${s.ai.reviewed_approved + s.ai.reviewed_rejected}</div><div class="muted">${s.ai.reviewed_approved} approved, ${s.ai.reviewed_rejected} rejected, ${s.ai.waiting_for_review} waiting</div></div></div>
    <section class="card"><div class="card-h"><h3>Export</h3></div><p class="muted" style="margin-bottom:12px">Files are built from the live database when you click. ${s.readings_stored.toLocaleString()} sensor readings are stored.</p>
      <div class="item-actions" style="margin:0"><button class="btn" id="exA"><i class="fa-solid fa-download"></i> Assets (CSV)</button><button class="btn" id="exL"><i class="fa-solid fa-download"></i> Alerts (CSV)</button><button class="btn" id="exS"><i class="fa-solid fa-download"></i> Summary (JSON)</button></div></section>`;
  return { html, mount: (v) => {
    $('#exA', v).onclick = async () => { const a = await GET('/assets'); download('nexora-assets.csv', toCSV(a, ['tag', 'name', 'type', 'plant', 'location', 'serial', 'health', 'status', 'vibration', 'temperature', 'pressure', 'flow_rate']), 'text/csv'); toast('Assets exported'); };
    $('#exL', v).onclick = async () => { const a = await GET('/alerts?status='); download('nexora-alerts.csv', toCSV(a, ['id', 'asset_tag', 'severity', 'title', 'status', 'source', 'ai_review', 'created_at', 'description']), 'text/csv'); toast('Alerts exported'); };
    $('#exS', v).onclick = () => { download('nexora-summary.json', JSON.stringify(s, null, 2), 'application/json'); toast('Summary exported'); };
  } };
};

/* ---------- integrations ---------- */
function openIntegrationForm(i) {
  formDialog({ title: i ? 'Edit integration' : 'Add integration', submit: i ? 'Save changes' : 'Add integration', values: i || { kind: 'CMMS', status: 'connected' },
    fields: [{ name: 'name', label: 'Name', required: true, max: 80 }, { name: 'kind', label: 'Kind', max: 30, hint: 'For example CMMS, ERP, Messaging, Telemetry' },
      { name: 'detail', label: 'Notes', max: 160, hint: 'Do not paste passwords or API keys here.' }, { name: 'status', label: 'Status', type: 'select', options: [['connected', 'Connected'], ['disconnected', 'Disconnected']] }],
    onSubmit: async (v) => { if (i) await PUT('/integrations/' + i.id, v); else await POST('/integrations', v); toast(i ? 'Integration updated' : 'Integration added'); render(true); } });
}
VIEWS.integrations = async () => {
  const list = await GET('/integrations');
  const html = `<div class="note">These are connection records for your team. No live connectors ship in this build; sensor data arrives through the REST API.</div>
    <div class="toolbar"><span class="grow"></span><button class="btn primary" id="newInt"><i class="fa-solid fa-plus"></i> Add integration</button></div>
    ${list.length ? `<div class="grid-2">${list.map((i) => `<section class="card"><div class="card-h"><h3 style="text-transform:none;font-size:14px;letter-spacing:0">${esc(i.name)}</h3><span class="chip ${i.status}">${cap(i.status)}</span></div>
      <p class="muted">${esc(i.kind)}${i.detail ? ' &bull; ' + esc(i.detail) : ''}</p><div class="item-actions"><button class="btn sm" data-toggle="${i.id}" data-st="${i.status}">${i.status === 'connected' ? 'Disconnect' : 'Connect'}</button>
      <button class="btn sm" data-edit="${i.id}">Edit</button><button class="btn sm danger" data-del="${i.id}" aria-label="Delete integration"><i class="fa-solid fa-trash"></i></button></div></section>`).join('')}</div>`
      : `<div class="card">${empty('No integrations', 'Add the systems your plant uses.')}</div>`}`;
  return { html, mount: (v) => {
    $('#newInt', v).onclick = () => openIntegrationForm();
    v.querySelectorAll('[data-toggle]').forEach((b) => (b.onclick = () => act(() => PATCH('/integrations/' + b.dataset.toggle, { status: b.dataset.st === 'connected' ? 'disconnected' : 'connected' }), 'Integration updated')));
    v.querySelectorAll('[data-edit]').forEach((b) => (b.onclick = () => openIntegrationForm(list.find((i) => i.id == b.dataset.edit))));
    v.querySelectorAll('[data-del]').forEach((b) => (b.onclick = async () => { if (await confirmDialog('Delete this integration?')) act(() => DEL('/integrations/' + b.dataset.del), 'Integration deleted'); }));
  } };
};

/* ---------- settings ---------- */
VIEWS.settings = async () => {
  const [c, m] = await Promise.all([GET('/settings'), GET('/metrics')]);
  const admin = S.user.role === 'admin';
  const dis = admin ? '' : 'disabled';
  const html = `${admin ? '' : '<div class="note">Alarm limits and KPIs can only be changed by an admin. You can still update your profile.</div>'}
    <div class="grid-2"><section class="card"><div class="card-h"><h3>Alarm limits</h3></div><form id="setForm">
      <div class="field"><label for="s_plant">Plant name</label><input id="s_plant" type="text" value="${esc(c.plant_name)}" maxlength="60" ${dis}></div>
      <div class="field"><label for="s_sens">Anomaly sensitivity</label><select id="s_sens" ${dis}>${[['strict', 'Strict (alarm at 85% of limit)'], ['standard', 'Standard'], ['relaxed', 'Relaxed (alarm at 115% of limit)']].map(([k, l]) => `<option value="${k}" ${k === c.sensitivity ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      <div class="field"><label for="s_vib">Vibration alarm (mm/s)</label><input id="s_vib" type="number" step="0.1" min="0.1" value="${c.vibration_alarm}" ${dis}></div>
      <div class="field"><label for="s_temp">Temperature alarm (\u00b0C)</label><input id="s_temp" type="number" step="1" min="1" value="${c.temperature_alarm}" ${dis}></div>
      <div class="field"><label class="check"><input type="checkbox" id="s_auto" ${c.auto_work_order ? 'checked' : ''} ${dis}> Log a work order when a critical alert is raised</label><span class="hint">Applies to threshold alerts only. AI suggestions always need approval.</span></div>
      <div class="form-err hidden" id="setErr" role="alert"></div><button class="btn primary" ${dis}>Save settings</button></form></section>
    <div><section class="card" style="margin-bottom:12px"><div class="card-h"><h3>Plant KPIs</h3></div><p class="muted" style="margin-bottom:12px">MTBF, OEE and energy need a plant data source. Until one is connected, an admin can enter them here.</p>
      <form id="kpiForm">${[['mtbf', 'MTBF (days)'], ['oee', 'OEE (%)'], ['energy', 'Energy (MWh)']].map(([k, l]) => `<div class="grid-2"><div class="field"><label for="k_${k}">${l}</label><input id="k_${k}" type="number" step="0.01" min="0" value="${m[k] ? m[k].value : 0}" ${dis}></div>
        <div class="field"><label for="d_${k}">Change vs previous period (%)</label><input id="d_${k}" type="number" step="0.1" value="${m[k] ? m[k].delta : 0}" ${dis}></div></div>`).join('')}
        <div class="form-err hidden" id="kpiErr" role="alert"></div><button class="btn primary" ${dis}>Save KPIs</button></form></section>
      <section class="card"><div class="card-h"><h3>Your profile</h3></div><form id="profForm"><div class="field"><label for="p_name">Name</label><input id="p_name" type="text" value="${esc(S.user.name)}" maxlength="80"></div>
        <div class="field"><label for="p_pass">New password</label><input id="p_pass" type="password" autocomplete="new-password" placeholder="Leave blank to keep the current one"><span class="hint">At least 8 characters.</span></div>
        <div class="form-err hidden" id="profErr" role="alert"></div><button class="btn primary">Save profile</button></form></section></div></div>`;
  const submit = (form, errId, fn, okMsg) => $(form).addEventListener('submit', async (e) => { e.preventDefault(); const err = $(errId); err.classList.add('hidden');
    try { await fn(); toast(okMsg); render(true); } catch (x) { err.textContent = x.message; err.classList.remove('hidden'); } });
  return { html, mount: () => {
    submit('#setForm', '#setErr', () => PUT('/settings', { plant_name: $('#s_plant').value.trim(), sensitivity: $('#s_sens').value, vibration_alarm: Number($('#s_vib').value), temperature_alarm: Number($('#s_temp').value), auto_work_order: $('#s_auto').checked }), 'Settings saved');
    submit('#kpiForm', '#kpiErr', async () => { for (const k of ['mtbf', 'oee', 'energy']) await PUT('/metrics/' + k, { value: Number($('#k_' + k).value), delta: Number($('#d_' + k).value) }); }, 'KPIs saved');
    submit('#profForm', '#profErr', async () => { const body = { name: $('#p_name').value.trim() }; if ($('#p_pass').value) body.password = $('#p_pass').value; S.user = await PATCH('/auth/me', body); $('#uName').textContent = S.user.name; $('#p_pass').value = ''; }, 'Profile saved');
  } };
};

/* ------------------------------------------------------------------ boot */
(async function boot() {
  setAuthMode('login');
  if (!S.token) { $('#auth').classList.remove('hidden'); return; }
  try { S.user = await GET('/auth/me'); enterApp(); }
  catch { $('#auth').classList.remove('hidden'); }
})();
