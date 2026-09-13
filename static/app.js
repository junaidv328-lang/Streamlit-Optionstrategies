const $ = (id) => document.getElementById(id);

const fmt = (n, digits = 2) =>
  n === null || n === undefined || Number.isNaN(n) ? '—' : Number(n).toFixed(digits);

const fmtPrice = (n) => (n === null || n === undefined ? '—' : `₹${fmt(n)}`);

function showStatus(message, isError = false) {
  const el = $('statusBanner');
  el.textContent = message;
  el.classList.remove('hidden');
  el.classList.toggle('error', isError);
}

function hideStatus() {
  $('statusBanner').classList.add('hidden');
}

let CATALOG = [];

// ---- Connection gate ----

async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.connected) {
      enterApp(data.client_code);
    }
  } catch (err) {
    // Leave the connect panel showing -- it'll surface the error on click instead.
  }
}

function enterApp(clientCode) {
  $('connectPanel').classList.add('hidden');
  $('mainControls').classList.remove('hidden');
  $('connectedAs').textContent = clientCode ? `Connected as ${clientCode}` : 'Connected';
  loadExpiries();
  loadCatalog();
  loadVix();
}

$('connectBtn').addEventListener('click', async () => {
  const btn = $('connectBtn');
  const errEl = $('connectError');
  btn.disabled = true;
  btn.textContent = 'Connecting…';
  errEl.classList.add('hidden');
  try {
    const res = await fetch('/api/login', { method: 'POST' });
    const data = await res.json();
    if (!data.connected) throw new Error(data.error || 'Login failed');
    enterApp(data.client_code);
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Connect to Angel One';
  }
});

// ---- Tabs ----

function activateTab(which) {
  const guided = which === 'guided';
  $('tabGuided').classList.toggle('active', guided);
  $('tabBrowse').classList.toggle('active', !guided);
  $('guidedForm').classList.toggle('hidden', !guided);
  $('browseForm').classList.toggle('hidden', guided);
}
$('tabGuided').addEventListener('click', () => activateTab('guided'));
$('tabBrowse').addEventListener('click', () => activateTab('browse'));

// ---- Data loading ----

async function loadVix() {
  try {
    const res = await fetch('/api/vix');
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    $('vixValue').textContent = `${fmt(data.vix, 2)} (${data.iv_regime === 'low' ? 'Low' : 'High'} IV)`;
  } catch (err) {
    $('vixValue').textContent = '—';
  }
}

async function loadExpiries() {
  try {
    const res = await fetch('/api/expiries');
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    [$('expiryGuided'), $('expiryBrowse')].forEach((select) => {
      select.innerHTML = '';
      data.forEach((exp) => {
        const opt = document.createElement('option');
        opt.value = exp;
        opt.textContent = exp;
        select.appendChild(opt);
      });
    });
  } catch (err) {
    showStatus(`Couldn't load expiries: ${err.message}`, true);
  }
}

async function loadCatalog() {
  try {
    const res = await fetch('/api/strategies');
    CATALOG = await res.json();
    const select = $('strategyPicker');
    select.innerHTML = '';
    let currentGroup = null;
    let optgroup = null;
    CATALOG.forEach((s) => {
      if (s.category !== currentGroup) {
        currentGroup = s.category;
        optgroup = document.createElement('optgroup');
        optgroup.label = currentGroup;
        select.appendChild(optgroup);
      }
      const opt = document.createElement('option');
      opt.value = s.key;
      opt.textContent = s.name + (s.multi_expiry ? ' (2 expiries)' : '');
      optgroup.appendChild(opt);
    });
    updateStrategyHint();
  } catch (err) {
    showStatus(`Couldn't load the strategy catalog: ${err.message}`, true);
  }
}

function updateStrategyHint() {
  const key = $('strategyPicker').value;
  const entry = CATALOG.find((s) => s.key === key);
  $('strategyHint').textContent = entry ? entry.description : '';
}
$('strategyPicker').addEventListener('change', updateStrategyHint);

// ---- Rendering ----

function renderStrategy(data) {
  $('strategyCard').classList.remove('hidden');
  $('strategyTag').textContent = data.strategy.replace(/_/g, ' ');
  $('strategyName').textContent = data.strategy_name;
  $('strategyDesc').textContent = data.description;

  const regimeEl = $('regimeNote');
  if (data.vix !== null && data.vix !== undefined) {
    const dirLabel = $('direction') && !$('guidedForm').classList.contains('hidden')
      ? $('direction').value : null;
    regimeEl.textContent = dirLabel
      ? `Predicted ${dirLabel} · India VIX ${fmt(data.vix, 2)} → classified ${data.iv_regime === 'low' ? 'Low' : 'High'} IV → this strategy.`
      : `India VIX right now: ${fmt(data.vix, 2)} (${data.iv_regime === 'low' ? 'Low' : 'High'} IV).`;
    regimeEl.classList.remove('hidden');
  } else {
    regimeEl.classList.add('hidden');
  }

  const noteEl = $('multiExpiryNote');
  if (data.multi_expiry) {
    noteEl.textContent = `Two-expiry strategy: front leg(s) at ${data.expiry}, far leg(s) at ${data.back_expiry}. ` +
      `Max profit/loss and the payoff curve value the far leg with Black-Scholes at today's IV — a theoretical estimate, not a forecast.`;
    noteEl.classList.remove('hidden');
  } else {
    noteEl.classList.add('hidden');
  }

  $('netPremium').textContent = `${fmtPrice(Math.abs(data.net_premium))} ${data.net_premium_type}`;
  $('maxProfit').textContent = fmtPrice(data.max_profit);
  $('maxLoss').textContent = fmtPrice(data.max_loss);
  $('breakevens').textContent = data.breakevens.length
    ? data.breakevens.map((b) => fmt(b, 0)).join(', ')
    : '—';

  const tbody = document.querySelector('#legsTable tbody');
  tbody.innerHTML = '';
  data.legs.forEach((leg) => {
    const tr = document.createElement('tr');
    const strikeLabel = leg.instr === 'FUT' ? '—' : fmt(leg.strike, 0);
    const typeLabel = leg.instr === 'FUT' ? 'FUT' : `${leg.instr}${leg.expiry_role === 'back' ? ' · far' : ''}`;
    const contractLabel = leg.symbol || '—';
    tr.innerHTML = `
      <td>${leg.action}</td>
      <td class="contract-cell">${contractLabel}</td>
      <td>${strikeLabel}</td>
      <td>${typeLabel}</td>
      <td>${leg.qty}</td>
      <td>${fmtPrice(leg.ltp)}</td>`;
    tbody.appendChild(tr);
  });

  $('spotValue').textContent = fmtPrice(data.spot);
  $('expiryValue').textContent = data.multi_expiry ? `${data.expiry} / ${data.back_expiry}` : data.expiry;
  if (data.vix !== null && data.vix !== undefined) {
    $('vixValue').textContent = `${fmt(data.vix, 2)} (${data.iv_regime === 'low' ? 'Low' : 'High'} IV)`;
  }

  drawPayoffChart(data.payoff_curve, data.spot);
}

function drawPayoffChart(curve, spot) {
  const canvas = $('payoffChart');
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  if (!curve || !curve.length) return;

  const xs = curve.map((p) => p[0]);
  const ys = curve.map((p) => p[1]);
  const lo = Math.min(...xs), hi = Math.max(...xs);
  let minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = Math.max(Math.abs(minY), Math.abs(maxY)) * 0.15 || 10;
  minY -= pad; maxY += pad;

  const marginL = 55, marginR = 20, marginT = 16, marginB = 26;
  const plotW = w - marginL - marginR, plotH = h - marginT - marginB;

  const xToPx = (x) => marginL + ((x - lo) / (hi - lo)) * plotW;
  const yToPx = (y) => marginT + (1 - (y - minY) / (maxY - minY)) * plotH;

  ctx.strokeStyle = '#2A303B';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(marginL, yToPx(0));
  ctx.lineTo(w - marginR, yToPx(0));
  ctx.stroke();

  ctx.strokeStyle = '#8B93A1';
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(xToPx(spot), marginT);
  ctx.lineTo(xToPx(spot), h - marginB);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.lineWidth = 2;
  for (let i = 1; i < curve.length; i++) {
    const [x0, y0] = curve[i - 1];
    const [x1, y1] = curve[i];
    ctx.strokeStyle = (y0 + y1) / 2 >= 0 ? '#4E9E77' : '#C0503F';
    ctx.beginPath();
    ctx.moveTo(xToPx(x0), yToPx(y0));
    ctx.lineTo(xToPx(x1), yToPx(y1));
    ctx.stroke();
  }

  ctx.fillStyle = '#8B93A1';
  ctx.font = '11px IBM Plex Mono, monospace';
  ctx.textAlign = 'center';
  ctx.fillText(fmt(lo, 0), marginL + 10, h - 8);
  ctx.fillText(fmt(hi, 0), w - marginR - 10, h - 8);
  ctx.fillText(`spot ${fmt(spot, 0)}`, xToPx(spot), marginT + 12);

  ctx.textAlign = 'right';
  ctx.fillText(fmt(maxY, 0), marginL - 8, marginT + 10);
  ctx.fillText(fmt(minY, 0), marginL - 8, h - marginB);
}

function renderChain(chain, spot) {
  const tbody = document.querySelector('#chainTable tbody');
  tbody.innerHTML = '';
  const strikes = Object.keys(chain).map(Number).sort((a, b) => a - b);
  if (!strikes.length) { $('chainMeta').textContent = ''; return; }
  const atm = strikes.reduce((best, s) =>
    Math.abs(s - spot) < Math.abs(best - spot) ? s : best, strikes[0]);

  strikes.forEach((strike) => {
    const ce = chain[strike].CE || {};
    const pe = chain[strike].PE || {};
    const tr = document.createElement('tr');
    if (strike === atm) tr.classList.add('atm-row');
    tr.innerHTML = `
      <td class="call-side">${ce.volume ?? '—'}</td>
      <td class="call-side">${fmt(ce.iv, 1)}</td>
      <td class="call-side">${fmt(ce.delta, 2)}</td>
      <td class="call-side">${fmtPrice(ce.ltp)}</td>
      <td></td>
      <td class="strike">${fmt(strike, 0)}</td>
      <td></td>
      <td class="put-side">${fmtPrice(pe.ltp)}</td>
      <td class="put-side">${fmt(pe.delta, 2)}</td>
      <td class="put-side">${fmt(pe.iv, 1)}</td>
      <td class="put-side">${pe.volume ?? '—'}</td>`;
    tbody.appendChild(tr);
  });

  $('chainMeta').textContent = `${strikes.length} strikes`;
}

// ---- Requests ----

async function runRequest(url, btn) {
  btn.disabled = true;
  const originalLabel = btn.textContent;
  btn.textContent = 'Fetching…';
  hideStatus();
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    renderStrategy(data);
    renderChain(data.chain, data.spot);
  } catch (err) {
    showStatus(`Couldn't get that strategy: ${err.message}`, true);
  } finally {
    btn.disabled = false;
    btn.textContent = originalLabel;
  }
}

$('guidedForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const params = new URLSearchParams({
    expiry: $('expiryGuided').value,
    direction: $('direction').value,
    risk_pref: $('risk_pref').value,
  });
  runRequest(`/api/suggest?${params}`, $('suggestBtn'));
});

$('browseForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const params = new URLSearchParams({
    key: $('strategyPicker').value,
    expiry: $('expiryBrowse').value,
  });
  runRequest(`/api/strategy?${params}`, $('browseBtn'));
});

checkStatus();
