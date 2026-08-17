/* ---------- state ---------- */
const state = {
  movers: null,
  watchlist: null,
  market: 'crypto',
  selected: null,        // chosen search result to add
  watchlistItems: [],
  signals: null,
  sigMarket: 'stocks_in',
  sigFilter: 'all',
  funds: null,
  fundCat: 'All',
  selectedFund: null,
  alerts: [],
  alertSelected: null,   // asset chosen for custom alert
  notified: new Set(JSON.parse(localStorage.getItem('notifiedAlerts') || '[]')),
  screener: null,
  scrMarket: 'stocks_in',
  scrSort: 'score',
  scrFilter: 'all',
  btSel: null,           // backtest asset
  cpSel1: null, cpSel2: null,
  pnlHistory: [],
  market: null,
  portfolio: null,
  journal: null,
};

const MARKET_LABEL = { crypto: 'Crypto', stocks_in: 'Indian Stocks', stocks_us: 'US Stocks' };

/* ---------- helpers ---------- */
const $ = (id) => document.getElementById(id);

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || ('HTTP ' + r.status));
  return body;
}

function fmtMoney(x, cur) {
  if (x === null || x === undefined) return '—';
  const num = Number(x);
  const abs = Math.abs(num);
  let s;
  const dec = abs >= 100 ? 0 : abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  if (cur === 'INR') s = '₹' + abs.toLocaleString('en-IN', { maximumFractionDigits: dec });
  else s = '$' + abs.toLocaleString('en-US', { maximumFractionDigits: dec });
  return num < 0 ? '−' + s : s;
}

function fmtPct(x, signed = true) {
  if (x === null || x === undefined) return '—';
  const v = Number(x).toFixed(2);
  return (signed && x > 0 ? '+' : '') + v + '%';
}

const updown = (x) => (x >= 0 ? 'up' : 'down');

/* ---------- sparkline ---------- */
function drawSpark(canvas, data, width = 90, height = 28) {
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);
  if (!data || data.length < 2) {
    ctx.strokeStyle = '#3a4757';
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
    return;
  }
  const vals = data.filter((v) => v !== null && v !== undefined && !isNaN(v));
  if (vals.length < 2) return;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const last = vals[vals.length - 1];
  const first = vals[0];
  const color = last >= first ? '#16c784' : '#ea3943';

  const pts = vals.map((v, i) => [
    (i / (vals.length - 1)) * (width - 4) + 2,
    height - 4 - ((v - min) / range) * (height - 8),
  ]);

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.6;
  ctx.lineJoin = 'round';
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
  ctx.stroke();
}

/* ---------- movers rendering ---------- */
function moverRow(item, rank, type) {
  const row = document.createElement('div');
  row.className = 'mrow';
  row.innerHTML = `
    <span class="rank">${rank}</span>
    <canvas class="spark" width="90" height="28"></canvas>
    <div>
      <div class="name">${esc(item.name)}</div>
      <div class="sym">${esc(item.ticker || item.symbol)}</div>
    </div>
    <span class="price">${fmtMoney(item.price, item.currency)}</span>
    <span class="badge ${updown(item.change_pct)}">${fmtPct(item.change_pct)}</span>`;
  drawSpark(row.querySelector('canvas'), item.sparkline);
  row.addEventListener('click', () => openDetail(type, item.symbol || item.id || item.ticker));
  return row;
}

function renderMovers() {
  const grid = $('moversGrid');
  const data = state.movers;
  if (!data) {
    grid.innerHTML = '<div class="loader">Could not load market data.</div>';
    return;
  }
  const seg = data[state.market];
  if (!seg || !seg.gainers.length) {
    grid.innerHTML = '<div class="loader">No data for this market right now.</div>';
    return;
  }
  const type = state.market;
  grid.innerHTML = '';
  const gainCard = document.createElement('div');
  gainCard.className = 'panel-card gain';
  gainCard.innerHTML = '<h3>▲ Top Gainers (24h)</h3>';
  seg.gainers.forEach((it, i) => gainCard.appendChild(moverRow(it, i + 1, type)));

  const lossCard = document.createElement('div');
  lossCard.className = 'panel-card loss';
  lossCard.innerHTML = '<h3>▼ Top Losers (24h)</h3>';
  seg.losers.forEach((it, i) => lossCard.appendChild(moverRow(it, i + 1, type)));

  grid.appendChild(gainCard);
  grid.appendChild(lossCard);
}

/* ---------- watchlist rendering ---------- */
function renderTotals() {
  const t = (state.watchlist && state.watchlist.totals) || { INR: {}, USD: {} };
  const box = $('totalsRow');
  box.innerHTML = '';
  [['INR', '₹ Indian assets (stocks & crypto)'], ['USD', '$ US assets']].forEach(([cur, label]) => {
    const seg = t[cur];
    if (!seg || !seg.count) return;
    const pct = seg.invested ? (seg.pnl / seg.invested) * 100 : 0;
    const card = document.createElement('div');
    card.className = 'total-card';
    card.innerHTML = `
      <div class="tlabel">${label} · ${seg.count} pick${seg.count > 1 ? 's' : ''}</div>
      <div class="tbig ${updown(seg.pnl)}">${fmtMoney(seg.pnl, cur)}</div>
      <div class="tsub">Invested ${fmtMoney(seg.invested, cur)} · Now ${fmtMoney(seg.value, cur)} · <span class="${updown(pct)}">${fmtPct(pct)}</span></div>`;
    box.appendChild(card);
  });
}

function renderPicks() {
  const tbody = $('picksBody');
  const items = state.watchlistItems || [];
  $('pickCount').textContent = items.length || '';
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">Your picks will appear here. Add your first stock or coin above 👆</td></tr>';
    renderTotals();
    loadPortfolioHealth();
    return;
  }
  tbody.innerHTML = '';
  items.forEach((it) => {
    const tr = document.createElement('tr');
    const pnlCls = updown(it.pnl);
    tr.innerHTML = `
      <td>
        <div class="asset-cell">
          <canvas width="70" height="24"></canvas>
          <div>
            <div class="aname">${esc(it.name)}</div>
            <div class="asym">${esc(it.ticker || it.symbol)} · ${it.currency === 'INR' ? '₹' : '$'}</div>
          </div>
        </div>
      </td>
      <td class="num">${fmtMoney(it.buy_price, it.currency)}</td>
      <td class="num">${Number(it.qty).toLocaleString('en-IN')}</td>
      <td class="num">${fmtMoney(it.current_price, it.currency)}</td>
      <td class="num ${updown(it.change_pct)}">${fmtPct(it.change_pct)}</td>
      <td class="num">${fmtMoney(it.invested, it.currency)}</td>
      <td class="num">${fmtMoney(it.value, it.currency)}</td>
      <td class="num">
        <span class="pnl-badge ${pnlCls}">${fmtMoney(it.pnl, it.currency)}</span>
        <div class="${pnlCls}" style="font-size:11.5px">${fmtPct(it.pnl_pct)}</div>
      </td>
      <td><button class="xbtn" title="Remove">✕</button></td>`;
    drawSpark(tr.querySelector('canvas'), it.sparkline, 70, 24);
    tr.querySelector('.xbtn').addEventListener('click', async () => {
      try {
        state.watchlist = await getJSON('/api/watchlist/' + it.id, { method: 'DELETE' });
        state.watchlistItems = state.watchlist.items;
        renderPicks();
      } catch (e) { console.error(e); }
    });
    tr.querySelector('.asset-cell').addEventListener('click', () => openDetail(it.type, it.symbol));
    tbody.appendChild(tr);
  });
  renderTotals();
  loadPortfolioHealth();
}

/* ---------- detail modal ---------- */
async function openDetail(type, symbol) {
  const body = $('modalBody');
  $('modal').classList.remove('hidden');
  body.innerHTML = '<div class="loader">Loading…</div>';
  try {
    const d = await getJSON('/api/detail?type=' + encodeURIComponent(type) + '&symbol=' + encodeURIComponent(symbol));
    const cur = d.currency === 'INR' ? '₹' : '$';
    const inWatchlist = (state.watchlistItems || []).some((i) => i.symbol === symbol && i.type === type);
    body.innerHTML = `
      <div class="m-head">
        <div>
          <div class="m-name">${esc(d.name)}</div>
          <div class="m-sym">${esc(d.ticker || d.symbol)} · ${MARKET_LABEL[type] || type}</div>
        </div>
        <span class="badge ${updown(d.change_pct)}">${fmtPct(d.change_pct)}</span>
      </div>
      <div class="m-price">${fmtMoney(d.price, d.currency)}</div>
      <div class="m-change ${updown(d.change_pct)}">24h change</div>
      <div class="m-chart"><canvas id="detailChart" width="500" height="150" style="width:100%"></canvas>
        <div class="m-range"><span>7 days ago</span><span>today</span></div>
      </div>
      <div class="m-stats">
        <div class="m-stat"><div class="k">7d Low</div><div class="v">${fmtMoney(d.sparkline && d.sparkline.length ? Math.min(...d.sparkline) : null, d.currency)}</div></div>
        <div class="m-stat"><div class="k">7d High</div><div class="v">${fmtMoney(d.sparkline && d.sparkline.length ? Math.max(...d.sparkline) : null, d.currency)}</div></div>
      </div>
      <div id="candlesBox" class="candles-box"><div class="loader" style="padding:16px">Loading candles…</div></div>
      <div id="forecastBox" class="fc-box"></div>
      <div id="newsBox" class="news-box"><div class="loader" style="padding:12px">Loading news…</div></div>
      ${inWatchlist
        ? '<div class="msg ok">✓ Already in your watchlist</div>'
        : `<div class="m-add">
             <input id="dBuy" type="number" step="any" min="0" placeholder="Your buy price (${cur})">
             <input id="dQty" type="number" step="any" min="0" placeholder="Quantity">
             <button class="btn primary" id="dAdd">＋ Add to My Picks</button>
           </div>`}`;
    const cv = $('detailChart');
    if (cv) drawSpark(cv, d.sparkline, cv.width, cv.height);
    attachForecast(type, symbol, d.currency);
    attachTechnicals(type, symbol, d.currency);
    attachNews(type, symbol, d.name);
    const dAdd = $('dAdd');
    if (dAdd) {
      dAdd.addEventListener('click', async () => {
        const bp = parseFloat($('dBuy').value);
        const qty = parseFloat($('dQty').value);
        if (!(bp > 0) || !(qty > 0)) { alert('Enter a valid buy price and quantity.'); return; }
        try {
          await addPick({ type, symbol: d.symbol, ticker: d.ticker || d.symbol, name: d.name, buy_price: bp, qty, currency: d.currency });
          $('modal').classList.add('hidden');
          showMsg('Added ' + d.name + ' to your picks ✓', 'ok');
        } catch (e) { alert(e.message); }
      });
    }
  } catch (e) {
    body.innerHTML = '<div class="loader">Could not load details. Try again.</div>';
  }
}

/* ---------- add pick ---------- */
async function addPick(payload) {
  state.watchlist = await getJSON('/api/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  state.watchlistItems = state.watchlist.items;
  renderPicks();
}

function showMsg(text, kind) {
  const m = $('addMsg');
  m.textContent = text;
  m.className = 'msg ' + (kind || 'ok');
  m.classList.remove('hidden');
  setTimeout(() => m.classList.add('hidden'), 4000);
}

function selectResult(r) {
  state.selected = r;
  $('searchInput').value = '';
  $('searchResults').classList.add('hidden');
  $('buyPrice').disabled = false;
  $('qty').disabled = false;
  $('selectedInfo').classList.remove('hidden');
  $('selectedInfo').innerHTML =
    `Selected: <b>${esc(r.name)}</b> <span class="chip">${esc(r.ticker || r.symbol)} · ${r.market || ''} · ${r.currency === 'INR' ? '₹' : '$'}</span> — enter your buy price &amp; quantity`;
  $('buyPrice').placeholder = 'Buy price (' + (r.currency === 'INR' ? '₹' : '$') + ')';
}

/* ---------- search ---------- */
let searchTimer = null;
function setupSearch() {
  const input = $('searchInput');
  const box = $('searchResults');
  input.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = input.value.trim();
    if (q.length < 2) { box.classList.add('hidden'); return; }
    searchTimer = setTimeout(async () => {
      try {
        const data = await getJSON('/api/search?q=' + encodeURIComponent(q));
        box.innerHTML = '';
        if (!data.results.length) {
          box.innerHTML = '<div class="dd-empty">No results. Try "reliance", "bitcoin", "tata"…</div>';
        } else {
          data.results.forEach((r) => {
            const div = document.createElement('div');
            div.className = 'dd-item';
            div.innerHTML = `<div><div class="n">${esc(r.name)}</div><div class="s">${esc(r.ticker || r.symbol)} · ${esc(r.market || '')}</div></div>
                             <span class="dd-tag">${r.type === 'crypto' ? 'Crypto' : r.type === 'stock_in' ? 'NSE' : 'US'}</span>`;
            div.addEventListener('click', () => selectResult(r));
            box.appendChild(div);
          });
        }
        box.classList.remove('hidden');
      } catch (e) { box.classList.add('hidden'); }
    }, 300);
  });
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrap')) box.classList.add('hidden');
  });

  $('addBtn').addEventListener('click', async () => {
    if (!state.selected) return;
    const bp = parseFloat($('buyPrice').value);
    const qty = parseFloat($('qty').value);
    if (!(bp > 0) || !(qty > 0)) { showMsg('Enter a valid buy price and quantity.', 'err'); return; }
    try {
      await addPick({ ...state.selected, buy_price: bp, qty });
      state.selected = null;
      $('buyPrice').value = ''; $('qty').value = '';
      $('buyPrice').disabled = true; $('qty').disabled = true;
      $('addBtn').disabled = true;
      $('selectedInfo').classList.add('hidden');
      showMsg('Added to your picks ✓', 'ok');
    } catch (e) { showMsg(e.message, 'err'); }
  });
}

/* ---------- tabs ---------- */
/* Load a tab's data immediately when it is opened (so it always shows
   content right away — or starts loading and fills in within seconds). */
function ensureTabData(tab) {
  switch (tab) {
    case 'movers':
      if (!state.movers) loadMovers();
      if (!state.market) loadMarket();
      break;
    case 'signals':
      if (!state.signals || !(state.signals.stocks_in || []).length) loadSignals();
      break;
    case 'funds':
      if (!state.funds || !(state.funds.funds || []).length) loadFunds();
      break;
    case 'screener':
      if (!state.screener || !(state.screener.stocks_in || []).length) loadScreener();
      break;
    case 'planner':
      if (!state.funds || !(state.funds.funds || []).length) loadFunds();
      if (!state.signals || !(state.signals.stocks_in || []).length) loadSignals();
      break;
    case 'tools':
      loadPnlHistory();
      break;
    case 'journal':
      if (!state.journal) loadJournal();
      break;
    case 'picks':
      loadWatchlist();
      loadPortfolioHealth();
      break;
    case 'advisor':
      break;
  }
}

function setupTabs() {
  document.querySelectorAll('.tab').forEach((t) => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((x) => x.classList.remove('active'));
      document.querySelectorAll('.panel').forEach((x) => x.classList.remove('active'));
      t.classList.add('active');
      $('tab-' + t.dataset.tab).classList.add('active');
      ensureTabData(t.dataset.tab);   // load instantly on click
    });
  });
  document.querySelectorAll('#tab-movers .subtab').forEach((t) => {
    t.addEventListener('click', () => {
      document.querySelectorAll('#tab-movers .subtab').forEach((x) => x.classList.remove('active'));
      t.classList.add('active');
      state.market = t.dataset.market;
      renderMovers();
    });
  });
  document.querySelectorAll('#sigSubtabs .subtab').forEach((t) => {
    t.addEventListener('click', () => {
      document.querySelectorAll('#sigSubtabs .subtab').forEach((x) => x.classList.remove('active'));
      t.classList.add('active');
      state.sigMarket = t.dataset.market;
      renderSignals();
    });
  });
  $('sigFilter').addEventListener('change', () => {
    state.sigFilter = $('sigFilter').value;
    renderSignals();
  });
  ['amtInr', 'amtUsd'].forEach((id) => $(id).addEventListener('input', renderSignals));
  $('refreshBtn').addEventListener('click', loadAll);
  $('modalClose').addEventListener('click', () => $('modal').classList.add('hidden'));
  $('modal').addEventListener('click', (e) => { if (e.target === $('modal')) $('modal').classList.add('hidden'); });
}

/* ---------- signals (auto picks) ---------- */
const SIG_CLASS = { 'STRONG BUY': 'strongbuy', 'BUY': 'buy', 'HOLD': 'hold', 'SELL': 'sell', 'STRONG SELL': 'strongsell' };

function amtFor(currency) {
  const v = parseFloat(currency === 'INR' ? $('amtInr').value : $('amtUsd').value);
  return isFinite(v) && v > 0 ? v : (currency === 'INR' ? 10000 : 1000);
}

function renderSigSummary() {
  const box = $('sigSummary');
  const ov = (state.signals && state.signals.overview && state.signals.overview[state.sigMarket]);
  if (!ov || !ov.count) { box.innerHTML = ''; return; }
  const cur = state.sigMarket === 'stocks_us' ? '$' : '₹';
  const amount = amtFor(cur === '$' ? 'USD' : 'INR');
  let topHtml = '';
  if (ov.top) {
    const t = ov.top;
    const profit = amount * (t.pnl_pct_target || 0) / 100;
    const loss = amount * (t.pnl_pct_stop || 0) / 100;
    topHtml = `<div class="sig-card">
      <div class="stitle">⭐ Top pick today</div>
      <div class="big"><span class="buy">${esc(t.name)}</span> — ${t.signal}</div>
      <div class="detail">Score <b>${t.score}</b> · buy near <b>${fmtMoney(t.price, t.currency)}</b> ·
        target <b>${fmtMoney(t.target, t.currency)}</b> · stop-loss <b>${fmtMoney(t.stop, t.currency)}</b><br>
        Invest <b>${fmtMoney(amount, t.currency)}</b> → if target hit <b class="up">+${fmtMoney(profit, t.currency)}</b>,
        if stop hit <b class="down">${fmtMoney(loss, t.currency)}</b> · hold ${esc(t.hold_label)}</div>
    </div>`;
  }
  box.innerHTML = `
    <div class="sig-card">
      <div class="stitle">${esc(ov.label)} · today's scan</div>
      <div class="big"><span class="buy">${ov.buys} BUY</span> · ${ov.holds} HOLD · <span class="sell">${ov.sells} SELL</span> of ${ov.count}</div>
      <div class="detail">Average score <b>${ov.avg_score}</b> · average 24h move <b>${fmtPct(ov.avg_change)}</b></div>
    </div>
    ${topHtml}`;
}

function renderSignals() {
  const data = state.signals;
  const tbody = $('sigBody');
  if (!data) {
    tbody.innerHTML = '<tr><td colspan="15" class="empty">Analyzing the market… (first run takes ~15 seconds)</td></tr>';
    $('sigSummary').innerHTML = '';
    return;
  }
  renderSigSummary();
  let items = (data[state.sigMarket] || []);
  if (state.sigFilter !== 'all') items = items.filter((i) => i.signal === state.sigFilter);
  if (!items.length) {
    const err = data.error
      ? 'Could not reach the data source. Check your internet connection.'
      : 'No assets match this filter right now.';
    tbody.innerHTML = `<tr><td colspan="15" class="empty">${esc(err)}<br><br>
      <button class="btn primary" onclick="loadSignals()">↻ Retry now</button></td></tr>`;
    return;
  }
  tbody.innerHTML = '';
  items.forEach((it, idx) => {
    const cur = it.currency === 'INR' ? '₹' : '$';
    const amount = amtFor(it.currency);
    const profit = amount * (it.pnl_pct_target || 0) / 100;
    const loss = amount * (it.pnl_pct_stop || 0) / 100;
    const barCls = it.score >= 20 ? 'good' : it.score <= -20 ? 'bad' : 'mid';
    const trendCls = it.trend === 'Uptrend' ? 'up' : it.trend === 'Downtrend' ? 'down' : '';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="rank">${idx + 1}</td>
      <td>
        <div class="asset-cell" style="min-width:170px">
          <canvas width="64" height="22"></canvas>
          <div>
            <div class="aname">${esc(it.name)}</div>
            <div class="asym">${esc(it.ticker || it.symbol)}</div>
          </div>
        </div>
      </td>
      <td class="num">${fmtMoney(it.price, it.currency)}</td>
      <td><span class="scorebar"><span class="${barCls}" style="width:${Math.min(100, Math.abs(it.score))}%"></span></span><b>${it.score}</b></td>
      <td><span class="sig-badge ${SIG_CLASS[it.signal] || 'hold'}">${it.signal}</span></td>
      <td><span class="trend-pill ${trendCls}">${it.trend || '—'}</span></td>
      <td class="num ${it.rsi >= 70 ? 'down' : it.rsi <= 30 ? 'up' : ''}">${it.rsi ?? '—'}</td>
      <td class="num">${fmtMoney(it.entry, it.currency)}</td>
      <td class="num">${fmtMoney(it.stop, it.currency)}</td>
      <td class="num">${fmtMoney(it.target, it.currency)}</td>
      <td class="num">${it.rr ?? '—'}</td>
      <td style="font-size:12px;color:var(--muted)">${esc(it.hold_label)}</td>
      <td class="num"><span class="up">+${fmtMoney(profit, it.currency)}</span></td>
      <td class="num"><span class="down">${fmtMoney(loss, it.currency)}</span></td>
      <td><button class="bell-btn" title="Alert me when it hits target or stop-loss">🔔</button></td>`;
    drawSpark(tr.querySelector('canvas'), it.sparkline, 64, 22);
    tr.addEventListener('click', () => openDetail(it.type, it.symbol));
    tr.querySelector('.bell-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      await setTargetStopAlerts(it);
    });
    tbody.appendChild(tr);
  });
}

/* ---------- mutual funds ---------- */
const riskClass = (v) => (v == null ? '' : v >= 18 ? 'risk-high' : v >= 10 ? 'risk-med' : 'risk-low');

function compoundSIP(monthly, years, annualPct) {
  const r = Math.pow(1 + annualPct / 100, 1 / 12) - 1;   // monthly rate
  const n = years * 12;
  const invested = monthly * n;
  if (r <= 0) return { invested, value: invested, pct: annualPct };
  const fv = monthly * ((Math.pow(1 + r, n) - 1) / r) * (1 + r);
  return { invested, value: fv, pct: annualPct };
}

function renderSipCard() {
  const amt = parseFloat($('sipAmt').value) || 5000;
  const years = parseFloat($('sipYears').value) || 10;
  const f = state.selectedFund;
  const box = $('sipResult');
  const det = $('sipDetail');
  if (!f) {
    box.textContent = '—';
    det.textContent = 'Click a fund row to project its SIP.';
    return;
  }
  const cagr = f.r3y ?? f.r5y ?? f.r1y ?? 8;
  const r = compoundSIP(amt, years, cagr);
  const gain = r.value - r.invested;
  box.textContent = '₹' + Math.round(r.value).toLocaleString('en-IN') + ' (invest ₹' + Math.round(r.invested).toLocaleString('en-IN') + ')';
  det.innerHTML = `<b>${esc(f.name)}</b> · SIP ₹${Number(amt).toLocaleString('en-IN')}/month × ${years} yr @ ${cagr}% CAGR → est. gain <b class="up">₹${Math.round(gain).toLocaleString('en-IN')}</b> (lumpsum ₹${Math.round(r.invested * Math.pow(1 + cagr / 100, years)).toLocaleString('en-IN')})`;
}

function renderFunds() {
  const data = state.funds;
  const tbody = $('fundsBody');
  if (!data) {
    tbody.innerHTML = '<tr><td colspan="12" class="empty">Loading mutual fund data… (first load ~20s)</td></tr>';
    return;
  }
  const funds = data.funds || [];
  if (!funds.length) {
    tbody.innerHTML = '<tr><td colspan="12" class="empty">Could not load mutual fund data — check your internet connection.<br><br><button class="btn primary" onclick="loadFunds()">↻ Retry now</button></td></tr>';
    return;
  }
  // build category tabs once
  const cats = ['All', ...(data.categories || [])];
  const catBox = $('fundCats');
  catBox.innerHTML = '';
  cats.forEach((c) => {
    const b = document.createElement('button');
    b.className = 'subtab' + (state.fundCat === c ? ' active' : '');
    b.textContent = c;
    b.addEventListener('click', () => {
      state.fundCat = c;
      [...catBox.children].forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      renderFunds();
    });
    catBox.appendChild(b);
  });

  const list = funds.filter((f) => state.fundCat === 'All' || f.category === state.fundCat);
  tbody.innerHTML = '';
  list.forEach((f) => {
    const tr = document.createElement('tr');
    tr.className = 'fund-row' + (state.selectedFund && state.selectedFund.code === f.code ? ' selected' : '');
    tr.innerHTML = `
      <td><div class="aname">${esc(f.name)}</div><div class="asym">${esc(f.fund_house || '')} · NAV ${esc(f.nav_date)}</div></td>
      <td><span class="trend-pill">${esc(f.category)}</span></td>
      <td class="num">₹${Number(f.nav).toFixed(2)}</td>
      <td class="num ${updown(f.r1m)}">${fmtPct(f.r1m, false)}</td>
      <td class="num ${updown(f.r3m)}">${fmtPct(f.r3m, false)}</td>
      <td class="num ${updown(f.r6m)}">${fmtPct(f.r6m, false)}</td>
      <td class="num ${updown(f.r1y)}">${fmtPct(f.r1y, false)}</td>
      <td class="num ${updown(f.r3y)}">${fmtPct(f.r3y, false)}</td>
      <td class="num ${updown(f.r5y)}">${fmtPct(f.r5y, false)}</td>
      <td><span class="${riskClass(f.volatility)}">${f.volatility != null ? f.volatility + '%' : '—'}</span></td>
      <td class="num down">${f.max_drawdown != null ? '−' + f.max_drawdown + '%' : '—'}</td>
      <td><span class="scorebar"><span class="${f.score >= 65 ? 'good' : f.score >= 45 ? 'mid' : 'bad'}" style="width:${f.score}%"></span></span><b>${f.score}</b></td>
      <td><span class="rating-badge rating-${esc(f.rating)}">${f.rating}</span></td>`;
    tr.addEventListener('click', () => {
      state.selectedFund = f;
      renderFunds();
      renderSipCard();
    });
    tbody.appendChild(tr);
  });
}

let fundsTries = 0;
async function loadFunds() {
  try {
    const data = await getJSON('/api/funds');
    if (data && data.funds && data.funds.length) {
      fundsTries = 0;
      state.funds = data;
      renderFunds();
      renderSipCard();
      return;
    }
    fundsTries++;
    if (fundsTries > 6) {
      state.funds = { funds: [], categories: [], error: true };
      renderFunds();
      return;
    }
    setTimeout(loadFunds, 5000);
  } catch (e) {
    fundsTries++;
    if (fundsTries > 6) {
      state.funds = { funds: [], categories: [], error: true };
      renderFunds();
      return;
    }
    setTimeout(loadFunds, 5000);
  }
}

/* ---------- alerts ---------- */
function openAlerts() {
  $('alertsModal').classList.remove('hidden');
  loadAlerts();
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
}

function alertCondText(a) {
  const arrow = a.direction === 'above' ? 'rises to' : 'falls to';
  const cur = a.currency === 'INR' ? '₹' : '$';
  return `${arrow} ${cur}${Number(a.level).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

function renderAlerts() {
  const list = $('alertsList');
  const items = state.alerts || [];
  $('alertCount').textContent = items.filter((a) => !a.triggered).length || '';
  $('alertCount').classList.toggle('hidden', !items.filter((a) => !a.triggered).length);
  if (!items.length) {
    list.innerHTML = '<div class="dd-empty">No alerts yet. Set one above, or use the 🔔 on an Auto Pick.</div>';
    return;
  }
  list.innerHTML = '';
  items.forEach((a) => {
    const div = document.createElement('div');
    div.className = 'alert-item' + (a.triggered ? ' triggered' : '');
    const cur = a.currency === 'INR' ? '₹' : '$';
    div.innerHTML = `
      <div>
        <div class="a-name">${esc(a.name)} <span class="asym">${esc(a.ticker || a.symbol)}</span></div>
        <div class="a-cond">${alertCondText(a)}</div>
        ${a.triggered ? `<div class="a-cond up">✓ Triggered ${esc((a.triggered_at || '').slice(0, 16).replace('T', ' '))} @ ${cur}${Number(a.triggered_price).toLocaleString('en-IN')}</div>` : ''}
      </div>
      <span class="a-level">${cur}${Number(a.level).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
      <span class="a-state ${a.triggered ? 'fired' : 'waiting'}">${a.triggered ? 'HIT ✓' : 'waiting'}</span>
      <button class="xbtn" title="Remove">✕</button>`;
    div.querySelector('.xbtn').addEventListener('click', async () => {
      await getJSON('/api/alerts/' + a.id, { method: 'DELETE' }).then((d) => {
        state.alerts = d.alerts; renderAlerts();
      }).catch(() => {});
    });
    list.appendChild(div);
  });
}

async function loadAlerts() {
  try {
    const d = await getJSON('/api/alerts');
    state.alerts = d.alerts || [];
    renderAlerts();
    checkNewlyTriggered(state.alerts);
  } catch (e) { /* silent */ }
}

async function setTargetStopAlerts(it) {
  try {
    const d = await getJSON('/api/alerts/targetstop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: it.type, symbol: it.symbol, ticker: it.ticker, name: it.name,
        currency: it.currency, target: it.target, stop: it.stop,
      }),
    });
    state.alerts = d.alerts || [];
    renderAlerts();
    toast('🔔 Alerts set', `${it.name}: target ${fmtMoney(it.target, it.currency)} & stop-loss ${fmtMoney(it.stop, it.currency)}`);
    if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
  } catch (e) {
    toast('Could not set alert', e.message, true);
  }
}

function checkNewlyTriggered(items) {
  items.forEach((a) => {
    if (a.triggered && !state.notified.has(a.id)) {
      state.notified.add(a.id);
      localStorage.setItem('notifiedAlerts', JSON.stringify([...state.notified]));
      const cur = a.currency === 'INR' ? '₹' : '$';
      const msg = `${a.name} ${a.direction === 'above' ? 'rose above' : 'fell below'} ${cur}${Number(a.level).toLocaleString('en-IN')}`;
      toast('🎯 Alert hit!', msg);
      if ('Notification' in window && Notification.permission === 'granted') {
        try { new Notification('🎯 Price alert hit', { body: msg }); } catch (e) {}
      }
    }
  });
}

function toast(title, body, isErr) {
  const box = $('toasts');
  const t = document.createElement('div');
  t.className = 'toast';
  if (isErr) t.style.borderColor = 'var(--red)';
  t.innerHTML = `<div class="t-title">${esc(title)}</div><div class="t-body">${esc(body)}</div>`;
  box.appendChild(t);
  setTimeout(() => t.remove(), 6000);
}

/* custom alert creation */
function setupAlerts() {
  $('alertsBtn').addEventListener('click', openAlerts);
  $('alertsClose').addEventListener('click', () => $('alertsModal').classList.add('hidden'));
  $('alertsModal').addEventListener('click', (e) => { if (e.target === $('alertsModal')) $('alertsModal').classList.add('hidden'); });

  const input = $('aSearch');
  const box = document.createElement('div');
  box.className = 'dropdown hidden';
  input.parentElement.appendChild(box);   // .search-wrap is position:relative
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { box.classList.add('hidden'); return; }
    timer = setTimeout(async () => {
      try {
        const data = await getJSON('/api/search?q=' + encodeURIComponent(q));
        box.innerHTML = '';
        if (!data.results.length) {
          box.innerHTML = '<div class="dd-empty">No results</div>';
        } else {
          data.results.slice(0, 6).forEach((r) => {
            const div = document.createElement('div');
            div.className = 'dd-item';
            div.innerHTML = `<div><div class="n">${esc(r.name)}</div><div class="s">${esc(r.ticker || r.symbol)}</div></div><span class="dd-tag">${r.type === 'crypto' ? 'Crypto' : r.type === 'stock_in' ? 'NSE' : 'US'}</span>`;
            div.addEventListener('click', () => {
              state.alertSelected = r;
              input.value = r.name;
              box.classList.add('hidden');
              $('aSelected').classList.remove('hidden');
              $('aSelected').innerHTML = `Alert for: <b>${esc(r.name)}</b> <span class="chip">${esc(r.ticker || r.symbol)}</span>`;
              $('aAdd').disabled = false;
            });
            box.appendChild(div);
          });
        }
        box.classList.remove('hidden');
      } catch (e) { box.classList.add('hidden'); }
    }, 300);
  });
  document.addEventListener('click', (e) => { if (!e.target.closest('.alert-custom')) box.classList.add('hidden'); });

  $('aAdd').addEventListener('click', async () => {
    const r = state.alertSelected;
    const level = parseFloat($('aLevel').value);
    if (!r || !(level > 0)) { $('aMsg').textContent = 'Pick an asset and a valid price level.'; $('aMsg').className = 'msg err'; $('aMsg').classList.remove('hidden'); return; }
    try {
      const d = await getJSON('/api/alerts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: r.type, symbol: r.symbol, ticker: r.ticker, name: r.name,
          currency: r.currency, direction: $('aDir').value, level,
        }),
      });
      state.alerts = d.alerts || [];
      renderAlerts();
      $('aLevel').value = ''; $('aAdd').disabled = true;
      $('aSelected').classList.add('hidden'); input.value = '';
      $('aMsg').textContent = 'Alert set ✓'; $('aMsg').className = 'msg ok'; $('aMsg').classList.remove('hidden');
      setTimeout(() => $('aMsg').classList.add('hidden'), 3000);
    } catch (e) {
      $('aMsg').textContent = e.message; $('aMsg').className = 'msg err'; $('aMsg').classList.remove('hidden');
    }
  });
}

/* ---------- daily PDF report ---------- */
function setupPdf() {
  $('pdfBtn').addEventListener('click', async () => {
    $('pdfBtn').textContent = '⏳ Building…';
    $('pdfBtn').disabled = true;
    try {
      const r = await fetch('/api/report');
      if (!r.ok) throw new Error('Report failed: HTTP ' + r.status);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'daily_analysis_' + new Date().toISOString().slice(0, 10) + '.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast('📄 Report ready', 'Today\'s PDF has been downloaded.');
    } catch (e) {
      toast('Report failed', e.message, true);
    } finally {
      $('pdfBtn').textContent = '📄 PDF';
      $('pdfBtn').disabled = false;
    }
  });
}

/* ---------- generic asset search helper ---------- */
function attachAssetSearch(input, onSelect) {
  const wrap = input.parentElement;   // .search-wrap is position:relative
  const box = document.createElement('div');
  box.className = 'dropdown hidden';
  wrap.appendChild(box);
  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { box.classList.add('hidden'); return; }
    timer = setTimeout(async () => {
      try {
        const data = await getJSON('/api/search?q=' + encodeURIComponent(q));
        box.innerHTML = '';
        if (!data.results.length) {
          box.innerHTML = '<div class="dd-empty">No results</div>';
        } else {
          data.results.slice(0, 6).forEach((r) => {
            const div = document.createElement('div');
            div.className = 'dd-item';
            div.innerHTML = `<div><div class="n">${esc(r.name)}</div><div class="s">${esc(r.ticker || r.symbol)}</div></div>
                             <span class="dd-tag">${r.type === 'crypto' ? 'Crypto' : r.type === 'stock_in' ? 'NSE' : 'US'}</span>`;
            div.addEventListener('click', () => { input.value = r.name; box.classList.add('hidden'); onSelect(r); });
            box.appendChild(div);
          });
        }
        box.classList.remove('hidden');
      } catch (e) { box.classList.add('hidden'); }
    }, 300);
  });
  document.addEventListener('click', (e) => { if (!e.target.closest('.search-wrap')) box.classList.add('hidden'); });
}

/* ---------- screener ---------- */
function fmtCap(v, cur) {
  if (v == null) return '—';
  if (cur === 'INR') {
    if (v >= 1e12) return '₹' + (v / 1e12).toFixed(2) + 'L Cr';
    if (v >= 1e7) return '₹' + (v / 1e7).toFixed(0) + ' Cr';
    return '₹' + Math.round(v).toLocaleString('en-IN');
  }
  if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T';
  if (v >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
  return '$' + Math.round(v).toLocaleString();
}

function renderScreener() {
  const tbody = $('scrBody');
  const data = state.screener;
  if (!data) {
    tbody.innerHTML = '<tr><td colspan="12" class="empty">Loading fundamentals… (first load ~20s)</td></tr>';
    return;
  }
  let items = (data[state.scrMarket] || []).slice();
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="12" class="empty">No fundamental data yet — check your connection.<br><br><button class="btn primary" onclick="loadScreener()">↻ Retry now</button></td></tr>';
    return;
  }
  // filter
  if (state.scrFilter === 'undervalued') items = items.filter((i) => i.pe != null && i.pe < 20);
  else if (state.scrFilter === 'dividend') items = items.filter((i) => (i.div_yield || 0) > 0);
  else if (state.scrFilter === 'buy') items = items.filter((i) => ['BUY', 'STRONG BUY'].includes(i.signal));
  else if (state.scrFilter === 'nearhigh') items = items.filter((i) => i.hi52 && i.price && i.price >= i.hi52 * 0.93);
  // sort
  if (state.scrSort === 'pe') items.sort((a, b) => (a.pe ?? 1e9) - (b.pe ?? 1e9));
  else if (state.scrSort === 'div') items.sort((a, b) => (b.div_yield || 0) - (a.div_yield || 0));
  else if (state.scrSort === 'mcap') items.sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
  else items.sort((a, b) => (b.score || -999) - (a.score || -999));

  tbody.innerHTML = '';
  items.forEach((it) => {
    const cur = it.currency === 'INR' ? '₹' : '$';
    let pos = null;
    if (it.hi52 && it.lo52 && it.hi52 > it.lo52) {
      pos = ((it.price - it.lo52) / (it.hi52 - it.lo52)) * 100;
      pos = Math.max(0, Math.min(100, pos));
    }
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><div class="aname">${esc(it.name)}</div><div class="asym">${esc(it.symbol)}</div></td>
      <td class="num">${fmtMoney(it.price, it.currency)}</td>
      <td class="num">${it.pe != null ? it.pe.toFixed(1) : '—'}</td>
      <td class="num">${it.fwd_pe != null ? it.fwd_pe.toFixed(1) : '—'}</td>
      <td class="num">${fmtCap(it.market_cap, it.currency)}</td>
      <td class="num ${(it.div_yield || 0) > 0 ? 'up' : ''}">${it.div_yield != null ? it.div_yield + '%' : '—'}</td>
      <td class="num">${it.pb != null ? it.pb.toFixed(1) : '—'}</td>
      <td class="num">${fmtMoney(it.hi52, it.currency)}</td>
      <td class="num">${fmtMoney(it.lo52, it.currency)}</td>
      <td style="font-size:12px;color:var(--muted)">${esc(it.sector || '—')}</td>
      <td>${it.score != null ? `<span class="scorebar"><span class="${it.score >= 20 ? 'good' : it.score <= -20 ? 'bad' : 'mid'}" style="width:${Math.min(100, Math.abs(it.score))}%"></span></span><b>${it.score}</b>` : '—'}</td>
      <td>${it.signal ? `<span class="sig-badge ${SIG_CLASS[it.signal] || 'hold'}">${it.signal}</span>` : '—'}</td>`;
    tr.style.cursor = 'pointer';
    tr.addEventListener('click', () => openDetail(it.symbol.endsWith('.NS') || it.symbol.endsWith('.BO') ? 'stock_in' : 'stock_us', it.symbol));
    tbody.appendChild(tr);
  });
  // show a small range hint under 52w columns via title
  const posCol = $('scrBody').querySelectorAll('tr');
  items.forEach((it, idx) => {
    if (!it.hi52 || !it.lo52 || it.hi52 <= it.lo52) return;
    const p = Math.max(0, Math.min(100, ((it.price - it.lo52) / (it.hi52 - it.lo52)) * 100));
    const row = posCol[idx];
    if (row) {
      const cell = row.children[7];
      if (cell) cell.title = `Price is at ${p.toFixed(0)}% of its 52-week range`;
    }
  });
}

let screenerTries = 0;
async function loadScreener() {
  try {
    const data = await getJSON('/api/screener');
    if (data && ((data.stocks_in && data.stocks_in.length) || (data.stocks_us && data.stocks_us.length))) {
      screenerTries = 0;
      state.screener = data;
      renderScreener();
      return;
    }
    screenerTries++;
    if (screenerTries > 6) {
      state.screener = { stocks_in: [], stocks_us: [], error: true };
      renderScreener();
      return;
    }
    setTimeout(loadScreener, 6000);
  } catch (e) {
    screenerTries++;
    if (screenerTries > 6) {
      state.screener = { stocks_in: [], stocks_us: [], error: true };
      renderScreener();
      return;
    }
    setTimeout(loadScreener, 6000);
  }
}

function setupScreener() {
  document.querySelectorAll('#scrSubtabs .subtab').forEach((t) => {
    t.addEventListener('click', () => {
      document.querySelectorAll('#scrSubtabs .subtab').forEach((x) => x.classList.remove('active'));
      t.classList.add('active');
      state.scrMarket = t.dataset.market;
      renderScreener();
    });
  });
  $('scrSort').addEventListener('change', () => { state.scrSort = $('scrSort').value; renderScreener(); });
  $('scrFilter').addEventListener('change', () => { state.scrFilter = $('scrFilter').value; renderScreener(); });
}

/* ---------- tools: backtest / compare / pnl history ---------- */
function setupTools() {
  attachAssetSearch($('btSearch'), (r) => {
    state.btSel = r;
    $('btSelected').classList.remove('hidden');
    $('btSelected').innerHTML = `Backtesting: <b>${esc(r.name)}</b> <span class="chip">${esc(r.ticker || r.symbol)}</span>`;
    $('btRun').disabled = false;
  });
  attachAssetSearch($('cpSearch1'), (r) => {
    state.cpSel1 = r;
    $('cpSelected').classList.remove('hidden');
    $('cpSelected').innerHTML = `Comparing: <b>${esc(r.name)}</b> <span class="chip">A</span>`;
    $('cpRun').disabled = !(state.cpSel1 && state.cpSel2);
  });
  attachAssetSearch($('cpSearch2'), (r) => {
    state.cpSel2 = r;
    $('cpSelected').classList.remove('hidden');
    const cur = $('cpSelected').innerHTML;
    $('cpSelected').innerHTML = cur + ` vs <b>${esc(r.name)}</b> <span class="chip">B</span>`;
    $('cpRun').disabled = !(state.cpSel1 && state.cpSel2);
  });

  $('btRun').addEventListener('click', runBacktest);
  $('cpRun').addEventListener('click', runCompare);
  $('pnlSnap').addEventListener('click', async () => {
    const d = await getJSON('/api/pnlhistory', { method: 'POST' });
    state.pnlHistory = d.history || [];
    renderPnlHistory();
  });
  $('pnlClear').addEventListener('click', async () => {
    const d = await getJSON('/api/pnlhistory', { method: 'DELETE' });
    state.pnlHistory = d.history || [];
    renderPnlHistory();
  });
}

async function runBacktest() {
  if (!state.btSel) return;
  const r = state.btSel;
  const amount = parseFloat($('btAmount').value) || 10000;
  const days = parseInt($('btPeriod').value) || 365;
  const box = $('btResult');
  box.innerHTML = '<div class="stitle">Calculating…</div>';
  try {
    const d = await getJSON(`/api/backtest?type=${encodeURIComponent(r.type)}&symbol=${encodeURIComponent(r.symbol)}&amount=${amount}&days=${days}`);
    const cur = r.currency === 'INR' ? '₹' : '$';
    const pnlCls = updown(d.pnl);
    box.innerHTML = `
      <div class="bt-head">
        <div>
          <div class="stitle">${esc(r.name)} · ${days === 30 ? '1M' : days === 90 ? '3M' : days === 180 ? '6M' : days === 365 ? '1Y' : days === 1095 ? '3Y' : '5Y'} ago → today</div>
          <div class="bt-big ${pnlCls}">${fmtMoney(d.value, r.currency)}</div>
          <div class="bt-sub">Invested ${fmtMoney(d.amount, r.currency)} → ${fmtMoney(d.pnl, r.currency)} (${fmtPct(d.pnl_pct)})</div>
        </div>
      </div>
      <canvas width="820" height="140" style="width:100%"></canvas>
      <div class="bt-grid">
        <div class="bt-stat"><div class="k">Start price</div><div class="v">${fmtMoney(d.start_price, r.currency)}</div></div>
        <div class="bt-stat"><div class="k">Now</div><div class="v">${fmtMoney(d.end_price, r.currency)}</div></div>
        <div class="bt-stat"><div class="k">Total return</div><div class="v ${pnlCls}">${fmtPct(d.pnl_pct)}</div></div>
        <div class="bt-stat"><div class="k">Annualised (CAGR)</div><div class="v ${pnlCls}">${fmtPct(d.cagr)}</div></div>
      </div>`;
    const cv = box.querySelector('canvas');
    drawSpark(cv, d.sparkline, cv.width, cv.height);
  } catch (e) {
    box.innerHTML = `<div class="stitle down">Backtest failed: ${esc(e.message)}</div>`;
  }
}

async function runCompare() {
  const a = state.cpSel1, b = state.cpSel2;
  if (!a || !b) return;
  const box = $('cpResult');
  box.innerHTML = '<div class="stitle">Comparing…</div>';
  try {
    const d = await getJSON(`/api/compare?type1=${encodeURIComponent(a.type)}&symbol1=${encodeURIComponent(a.symbol)}&type2=${encodeURIComponent(b.type)}&symbol2=${encodeURIComponent(b.symbol)}`);
    const sa = d.a.stats, sb = d.b.stats;
    box.innerHTML = `
      <canvas id="cpChart" width="820" height="180" style="width:100%"></canvas>
      <div class="legend">
        <span><span class="sw" style="background:#3b82f6"></span>${esc(a.name)}</span>
        <span><span class="sw" style="background:#f59e0b"></span>${esc(b.name)}</span>
      </div>
      <table class="compare-table">
        <tr><th>Metric (90d)</th><th style="color:#3b82f6">${esc(a.name)}</th><th style="color:#f59e0b">${esc(b.name)}</th></tr>
        <tr><td>Return</td><td class="${updown(sa.ret)}">${fmtPct(sa.ret)}</td><td class="${updown(sb.ret)}">${fmtPct(sb.ret)}</td></tr>
        <tr><td>Volatility (annual)</td><td>${sa.vol != null ? sa.vol + '%' : '—'}</td><td>${sb.vol != null ? sb.vol + '%' : '—'}</td></tr>
        <tr><td>Max drawdown</td><td class="down">−${sa.mdd}%</td><td class="down">−${sb.mdd}%</td></tr>
      </table>`;
    drawCompareChart($('cpChart'), d.a.norm, d.b.norm);
  } catch (e) {
    box.innerHTML = `<div class="stitle down">Compare failed: ${esc(e.message)}</div>`;
  }
}

function drawCompareChart(canvas, na, nb) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const all = na.concat(nb);
  const min = Math.min(...all), max = Math.max(...all);
  const range = (max - min) || 1;
  const pad = 24;
  const stepX = (W - pad * 2) / Math.max(1, na.length - 1);
  const y = (v) => H - pad - ((v - min) / range) * (H - pad * 2);
  // base 100 line
  const y100 = y(100);
  ctx.strokeStyle = '#3a4757'; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(pad, y100); ctx.lineTo(W - pad, y100); ctx.stroke();
  ctx.setLineDash([]);
  [[na, '#3b82f6'], [nb, '#f59e0b']].forEach(([arr, col]) => {
    ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath();
    arr.forEach((v, i) => { const x = pad + i * stepX; i === 0 ? ctx.moveTo(x, y(v)) : ctx.lineTo(x, y(v)); });
    ctx.stroke();
  });
  ctx.fillStyle = '#8b98a5'; ctx.font = '11px sans-serif';
  ctx.fillText('100 = start', pad, y100 - 4);
}

function renderPnlHistory() {
  const hist = state.pnlHistory || [];
  const wrap = $('pnlList');
  if (!hist.length) {
    wrap.innerHTML = '<div class="stitle">No history yet — add picks to My Picks and it will start tracking daily.</div>';
  } else {
    wrap.innerHTML = '';
    [...hist].reverse().forEach((e) => {
      const inr = e.inr_value > 0 || e.inr_invested > 0 ? `<span class="${updown(e.inr_pnl)}">₹${Math.round(e.inr_pnl).toLocaleString('en-IN')}</span>` : '';
      const usd = e.usd_value > 0 || e.usd_invested > 0 ? `<span class="${updown(e.usd_pnl)}">$${Math.round(e.usd_pnl).toLocaleString('en-US')}</span>` : '';
      const div = document.createElement('div');
      div.className = 'pnl-entry';
      div.innerHTML = `<span class="d">${e.date}</span><span>${inr} ${usd}</span><span class="d">${e.n_items} picks</span>`;
      wrap.appendChild(div);
    });
  }
  drawPnlChart();
}

function drawPnlChart() {
  const cv = $('pnlChart');
  if (!cv) return;
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  const hist = state.pnlHistory || [];
  if (!hist.length) {
    ctx.fillStyle = '#8b98a5'; ctx.font = '12px sans-serif';
    ctx.fillText('Add picks to My Picks to start tracking daily P&L', 30, H / 2);
    return;
  }
  const hasInr = hist.some((e) => (e.inr_value || 0) > 0 || (e.inr_invested || 0) > 0);
  const vals = hist.map((e) => hasInr ? e.inr_pnl : e.usd_pnl);
  const min = Math.min(0, ...vals), max = Math.max(0, ...vals);
  const range = (max - min) || 1;
  const pad = 24;
  const stepX = (W - pad * 2) / Math.max(1, vals.length - 1);
  const y = (v) => H - pad - ((v - min) / range) * (H - pad * 2);
  const y0 = y(0);
  ctx.strokeStyle = '#3a4757'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, y0); ctx.lineTo(W - pad, y0); ctx.stroke();
  ctx.strokeStyle = vals[vals.length - 1] >= vals[0] ? '#16c784' : '#ea3943';
  ctx.lineWidth = 2;
  ctx.beginPath();
  vals.forEach((v, i) => { const x = pad + i * stepX; i === 0 ? ctx.moveTo(x, y(v)) : ctx.lineTo(x, y(v)); });
  ctx.stroke();
  ctx.fillStyle = '#8b98a5'; ctx.font = '11px sans-serif';
  ctx.fillText((hasInr ? '₹' : '$') + Math.round(max).toLocaleString(), pad, 12);
  ctx.fillText((hasInr ? '₹' : '$') + Math.round(min).toLocaleString(), pad, H - 10);
  if (hist.length > 1) {
    ctx.fillText(hist[0].date.slice(5), pad, H - 4);
    ctx.fillText(hist[hist.length - 1].date.slice(5), W - pad - 40, H - 4);
  }
}

async function loadPnlHistory() {
  try {
    const d = await getJSON('/api/pnlhistory');
    state.pnlHistory = d.history || [];
    renderPnlHistory();
  } catch (e) { /* silent */ }
}

/* ---------- forecast (in detail modal) ---------- */
async function attachForecast(type, symbol, currency) {
  const el = document.getElementById('forecastBox');
  if (!el) return;
  el.innerHTML = '<div class="stitle">🔮 Loading forecast…</div>';
  try {
    const f = await getJSON(`/api/forecast?type=${encodeURIComponent(type)}&symbol=${encodeURIComponent(symbol)}`);
    const cur = currency === 'INR' ? '₹' : '$';
    const dirCls = f.direction === 'Uptrend' ? 'up' : f.direction === 'Downtrend' ? 'down' : '';
    el.innerHTML = `
      <div class="fc-head">🔮 AI Price Forecast <span class="trend-pill ${dirCls}">${esc(f.direction)}</span></div>
      <div class="fc-grid">
        <div class="fc-cell">
          <div class="k">7 days</div>
          <div class="v">${fmtMoney(f.p7, currency)}</div>
          <div class="s ${updown(f.up7)}">${fmtPct(f.up7)}</div>
          <div class="rng">${fmtMoney(f.p7_low, currency)} – ${fmtMoney(f.p7_high, currency)}</div>
        </div>
        <div class="fc-cell">
          <div class="k">30 days</div>
          <div class="v">${fmtMoney(f.p30, currency)}</div>
          <div class="s ${updown(f.up30)}">${fmtPct(f.up30)}</div>
          <div class="rng">${fmtMoney(f.p30_low, currency)} – ${fmtMoney(f.p30_high, currency)}</div>
        </div>
      </div>
      <div class="fc-note">Statistical projection from ${f.days_used} days of trend + volatility — an estimate, not a promise. Range = ±1σ.</div>`;
  } catch (e) {
    el.innerHTML = '';
  }
}

/* ---------- candlestick chart ---------- */
function drawCandles(canvas, t) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const { opens, highs, lows, closes } = t.candles;
  const n = closes.length;
  if (n < 2) return;
  const vals = highs.concat(lows);
  const min = Math.min(...vals.filter((v) => v != null));
  const max = Math.max(...vals.filter((v) => v != null));
  const range = (max - min) || 1;
  const padL = 8, padR = 8, padT = 10, padB = 14;
  const bw = (W - padL - padR) / n;
  const y = (v) => padT + (max - v) / range * (H - padT - padB);
  // support / resistance lines
  const levels = [[t.support, '#d9a514'], [t.resistance, '#3b82f6']];
  levels.forEach(([lv, col]) => {
    if (lv == null) return;
    const yy = y(lv);
    ctx.strokeStyle = col; ctx.setLineDash([5, 4]); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = col; ctx.font = '10px sans-serif';
    ctx.fillText('S' , padL + 1, yy - 2);
    ctx.fillText('R', padL + 1, yy + (yy < H - 20 ? 10 : -2));
  });
  for (let i = 0; i < n; i++) {
    const o = opens[i], h = highs[i], l = lows[i], c = closes[i];
    if (o == null || h == null || l == null || c == null) continue;
    const x = padL + i * bw + bw * 0.5;
    const col = c >= o ? '#16c784' : '#ea3943';
    ctx.strokeStyle = col; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, y(h)); ctx.lineTo(x, y(l)); ctx.stroke();
    ctx.fillStyle = col;
    const bodyTop = y(Math.max(o, c)), bodyH = Math.max(1.5, Math.abs(y(o) - y(c)));
    ctx.fillRect(x - bw * 0.32, bodyTop, bw * 0.64, bodyH);
  }
}

function sigPill(signal) {
  return `<span class="sig-badge ${SIG_CLASS[signal] || 'hold'}">${signal}</span>`;
}

async function attachTechnicals(type, symbol, currency) {
  const box = $('candlesBox');
  if (!box) return;
  try {
    const t = await getJSON(`/api/technicals?type=${encodeURIComponent(type)}&symbol=${encodeURIComponent(symbol)}`);
    const cur = currency === 'INR' ? '₹' : '$';
    const pats = (t.patterns || []).map((p) => `<div class="pat"><b>${esc(p.name)}</b> — ${esc(p.meaning)}</div>`).join('') || '<div class="pat muted">No clear pattern today</div>';
    const rsiCls = t.rsi >= 70 ? 'down' : t.rsi <= 30 ? 'up' : '';
    const macdCls = t.macd.state && t.macd.state.includes('bullish') ? 'up' : 'down';
    box.innerHTML = `
      <div class="tc-head">📊 Candlesticks (60d) & Technicals</div>
      <div class="tc-chart"><canvas id="candleChart" width="520" height="180" style="width:100%"></canvas>
        <div class="legend"><span><span class="sw" style="background:#d9a514"></span>Support ${fmtMoney(t.support, currency)}</span>
        <span><span class="sw" style="background:#3b82f6"></span>Resistance ${fmtMoney(t.resistance, currency)}</span></div>
      </div>
      <div class="tc-grid">
        <div class="m-stat"><div class="k">RSI (14)</div><div class="v ${rsiCls}">${t.rsi ?? '—'} ${t.rsi >= 70 ? '· overbought' : t.rsi <= 30 ? '· oversold' : ''}</div></div>
        <div class="m-stat"><div class="k">MACD</div><div class="v ${macdCls}" style="font-size:13px">${t.macd.state || '—'}</div></div>
        <div class="m-stat"><div class="k">SMA 20 / 50</div><div class="v" style="font-size:13px">${fmtMoney(t.sma20, currency)} / ${fmtMoney(t.sma50, currency)}</div></div>
        <div class="m-stat"><div class="k">Crosses</div><div class="v" style="font-size:12.5px">${t.golden_cross ? '<span class="up">Golden cross ✚</span>' : t.death_cross ? '<span class="down">Death cross ☠</span>' : 'None recent'}</div></div>
      </div>
      <div class="tc-pats"><div class="k">Today's candle patterns</div>${pats}</div>`;
    drawCandles($('candleChart'), t);
  } catch (e) {
    box.innerHTML = '';
  }
}

async function attachNews(type, symbol, name) {
  const box = $('newsBox');
  if (!box) return;
  try {
    const d = await getJSON(`/api/news?type=${encodeURIComponent(type)}&symbol=${encodeURIComponent(symbol)}&name=${encodeURIComponent(name)}`);
    const s = d.sentiment || {};
    const cls = s.label === 'Positive' ? 'up' : s.label === 'Negative' ? 'down' : 'muted';
    let itemsHtml = (d.items || []).slice(0, 6).map((it) =>
      `<a class="news-item" href="${esc(it.url)}" target="_blank" rel="noopener">
        <div class="n-title">${esc(it.title)}</div>
        <div class="n-meta">${esc(it.source)} ${esc(it.date)}</div>
      </a>`).join('');
    if (!itemsHtml) itemsHtml = '<div class="pat muted">No news found</div>';
    box.innerHTML = `
      <div class="tc-head">📰 News & Sentiment <span class="sent-badge ${cls}">${esc(s.label)} ${s.score ? s.score + '%' : ''}</span></div>
      <div class="news-list">${itemsHtml}</div>
      <div class="fc-note">Headlines from Google News. Sentiment = simple keyword score (${s.positive || 0} positive / ${s.negative || 0} negative mentions).</div>`;
  } catch (e) {
    box.innerHTML = '';
  }
}

/* ---------- market mood ---------- */
function renderMarketMood() {
  const box = $('marketMood');
  if (!state.market) {
    box.innerHTML = '<div class="loader">Loading market mood…</div>';
    return;
  }
  const m = state.market;
  const indCards = (m.indices || []).map((i) => `
    <div class="idx-card ${updown(i.change_pct)}">
      <div class="i-name">${esc(i.name)}</div>
      <div class="i-price">${fmtMoney(i.price, i.currency)}</div>
      <div class="i-chg ${updown(i.change_pct)}">${fmtPct(i.change_pct)}</div>
    </div>`).join('');
  let breadthHtml = '';
  if (m.breadth) {
    const b = m.breadth;
    const advW = b.total ? (b.advancers / b.total * 100) : 0;
    breadthHtml = `
      <div class="breadth">
        <div class="b-title">NIFTY 50 breadth</div>
        <div class="b-bar"><span class="adv" style="width:${advW}%"></span><span class="dec" style="width:${100 - advW}%"></span></div>
        <div class="b-legend"><span class="up">▲ ${b.advancers} up</span><span class="down">▼ ${b.decliners} down</span><span class="muted">${b.unchanged} flat</span></div>
      </div>`;
  }
  const secBars = (m.sectors || []).slice(0, 6).map((s) => `
    <div class="sec-row">
      <span class="sec-name">${esc(s.sector)}</span>
      <div class="sec-track"><span class="${updown(s.change_pct)}" style="width:${Math.min(100, Math.abs(s.change_pct) * 12)}%"></span></div>
      <span class="sec-chg ${updown(s.change_pct)}">${fmtPct(s.change_pct)}</span>
    </div>`).join('');
  box.innerHTML = `
    <div class="mm-indices">${indCards}</div>
    ${breadthHtml ? `<div class="mm-breadth">${breadthHtml}</div>` : ''}
    <div class="mm-sectors">
      <div class="b-title">NIFTY sectors today</div>
      ${secBars || '<div class="muted">Sector data loading…</div>'}
    </div>`;
}

/* ---------- portfolio health & tax ---------- */
function renderPortfolioHealth() {
  const box = $('healthBox');
  if (!box) return;
  const data = state.portfolio;
  if (!data) {
    box.innerHTML = '<div class="health-card"><div class="stitle">Portfolio health — add picks to see risk, diversification & tax.</div></div>';
    return;
  }
  const h = data.health, tx = data.tax;
  let html = '';
  if (h) {
    html += `<div class="health-card">
      <div class="stitle">💪 Portfolio health</div>
      <div class="hc-grid">
        <div><div class="k">Diversification</div><div class="v">${h.diversification}% <span class="muted" style="font-size:11px">(${esc(h.divers_label)})</span></div></div>
        <div><div class="k">Weighted volatility</div><div class="v">${h.weighted_vol}% <span class="muted" style="font-size:11px">(${esc(h.risk_label)})</span></div></div>
        <div><div class="k">Largest holding</div><div class="v">${esc(h.top.name)} <span class="muted" style="font-size:11px">(${h.top.share}%)</span></div></div>
      </div>
      ${h.advice.length ? `<div class="hc-advice">${h.advice.map((a) => `<div>• ${esc(a)}</div>`).join('')}</div>` : ''}
    </div>`;
  }
  if (tx && tx.rows.length) {
    const t = tx.totals;
    html += `<div class="health-card">
      <div class="stitle">🧾 Capital-gains tax (India, if you sold today)</div>
      <div class="tax-total">Estimated tax: <b class="down">₹${Math.round(t.grand_total).toLocaleString('en-IN')}</b></div>
      <div class="tax-break">
        <div>Equity LTCG (12.5% after ₹1.25L): <b>₹${Math.round(t.equity_ltcg_tax).toLocaleString('en-IN')}</b></div>
        <div>Equity STCG (20%): <b>₹${Math.round(t.equity_stcg_tax).toLocaleString('en-IN')}</b></div>
        <div>Crypto (30% flat): <b>₹${Math.round(t.crypto_tax).toLocaleString('en-IN')}</b></div>
        <div>Foreign/US equity: <b>₹${Math.round(t.foreign_tax).toLocaleString('en-IN')}</b></div>
      </div>
      <div class="fc-note">Rates per FY 2026-27 (Budget 2026). Assumes slab ${t.slab_rate}% for foreign short-term. Estimate only — consult a CA.</div>
    </div>`;
  }
  box.innerHTML = html || '<div class="health-card"><div class="stitle">No gains yet — tax applies only to profits.</div></div>';
}

async function loadPortfolioHealth() {
  try {
    const data = await getJSON('/api/portfolio');
    state.portfolio = data;
    renderPortfolioHealth();
  } catch (e) {
    state.portfolio = null;
    renderPortfolioHealth();
  }
}

async function loadMarket() {
  try {
    state.market = await getJSON('/api/market');
    renderMarketMood();
  } catch (e) { /* silent */ }
}

/* ---------- AI advisor ---------- */
const ADVISOR_QUICK = [
  'Should I buy Reliance?', 'Best Indian stocks today', 'Best mutual funds',
  'I want ₹50 lakh in 10 years', 'How is my portfolio?', 'How is bitcoin?',
];

function chatAdd(role, text) {
  const box = $('chatBox');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

async function advisorAsk(question, auto) {
  const q = (question || $('chatInput').value).trim();
  if (!q) return;
  if (!auto) { chatAdd('user', q); $('chatInput').value = ''; }
  const typing = chatAdd('bot', 'Thinking…');
  try {
    const d = await getJSON('/api/advisor/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q }),
    });
    typing.remove();
    chatAdd('bot', d.answer);
    if (d.advice) renderAdviceCard(d.advice);
  } catch (e) {
    typing.remove();
    chatAdd('bot', 'Sorry, something went wrong. Try again.');
  }
}

function renderAdviceCard(rec) {
  const box = $('advResult');
  if (!box) return;
  const cur = rec.currency === 'INR' ? '₹' : '$';
  const vCls = ['STRONG BUY', 'BUY'].includes(rec.verdict) ? 'up' : ['STRONG SELL', 'SELL'].includes(rec.verdict) ? 'down' : 'hold';
  const barCls = rec.score >= 60 ? 'good' : rec.score >= 40 ? 'mid' : 'bad';
  const reasons = (rec.reasons || []).map((r) => `<li>${esc(r)}</li>`).join('');
  const risks = (rec.risks || []).map((r) => `<li>${esc(r)}</li>`).join('');
  box.innerHTML = `
    <div class="adv-card">
      <div class="aname">${esc(rec.name)} <span class="asym">${esc(rec.symbol)}</span></div>
      ${rec.price != null ? `<div class="muted" style="font-size:12px">Price: ${cur}${Number(rec.price).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</div>` : ''}
      <div class="adv-verdict ${vCls}">${rec.verdict}</div>
      <div class="muted" style="font-size:12px">Advisor score ${rec.score}/100</div>
      <div class="adv-scorebar"><span class="${barCls}" style="width:${rec.score}%"></span></div>
      ${rec.components ? `<div class="adv-comp">
        <span class="ac">Technical: ${esc(rec.components.technical || '—')}</span>
        <span class="ac">Fundamentals: ${rec.components.fundamental_score > 0 ? '+' : ''}${rec.components.fundamental_score}</span>
        <span class="ac">Forecast: ${esc(rec.components.forecast || '—')}</span>
      </div>` : ''}
      <div class="adv-sec"><div class="k">Why</div><ul>${reasons || '<li>—</li>'}</ul></div>
      ${risks ? `<div class="adv-sec"><div class="k">Risks</div><ul class="risks">${risks}</ul></div>` : ''}
    </div>`;
}

function setupAdvisor() {
  $('chatSend').addEventListener('click', () => advisorAsk(null, false));
  $('chatInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') advisorAsk(null, false); });
  document.querySelectorAll('#chatSuggest .chip-btn').forEach((b) => {
    b.addEventListener('click', () => advisorAsk(b.textContent, true));
  });
  attachAssetSearch($('advSearch'), (r) => getAdviceFor(r));
}

async function getAdviceFor(r) {
  const box = $('advResult');
  box.innerHTML = '<div class="stitle">Analyzing…</div>';
  try {
    const rec = await getJSON(`/api/advisor?type=${encodeURIComponent(r.type)}&symbol=${encodeURIComponent(r.symbol)}&name=${encodeURIComponent(r.name)}&currency=${encodeURIComponent(r.currency || 'INR')}`);
    renderAdviceCard(rec);
  } catch (e) {
    box.innerHTML = `<div class="stitle down">Could not get advice: ${esc(e.message)}</div>`;
  }
}

/* ---------- planner ---------- */
function setupPlanner() {
  $('pfRun').addEventListener('click', async () => {
    const box = $('pfResult');
    box.classList.remove('hidden');
    box.innerHTML = '<div class="stitle">Building your plan…</div>';
    try {
      const d = await getJSON('/api/planner/risk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          age: parseInt($('pfAge').value) || 30,
          horizon: parseInt($('pfHorizon').value) || 10,
          appetite: $('pfAppetite').value,
          stability: $('pfStability').value,
          amount: parseFloat($('pfAmount').value) || 100000,
        }),
      });
      const p = d.profile;
      const rows = d.plan.map((b) => `
        <tr>
          <td><b>${esc(b.bucket)}</b><div class="alloc-picks">${esc(b.suggestions.join(' · ') || '—')}</div></td>
          <td class="alloc-pct">${b.pct}%</td>
          <td class="alloc-amt">₹${Math.round(b.amount).toLocaleString('en-IN')}</td>
        </tr>`).join('');
      box.innerHTML = `
        <div class="gp-head ${p.label === 'Aggressive' ? 'up' : p.label === 'Conservative' ? 'down' : ''}">${esc(p.label)} profile (${p.score}/100)</div>
        <div class="gp-line muted" style="font-size:12px">${esc(p.explanation)}</div>
        <table class="alloc-table">
          <tr><th>Where</th><th>%</th><th class="alloc-amt">Amount</th></tr>
          ${rows}
        </table>
        <div class="fc-note">Suggestions use today's real fund & stock rankings. Not financial advice.</div>`;
    } catch (e) {
      box.innerHTML = `<div class="stitle down">Failed: ${esc(e.message)}</div>`;
    }
  });

  $('gpRun').addEventListener('click', async () => {
    const box = $('gpResult');
    box.classList.remove('hidden');
    box.innerHTML = '<div class="stitle">Calculating…</div>';
    try {
      const d = await getJSON('/api/planner/goal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: parseFloat($('gpTarget').value) || 0,
          years: parseInt($('gpYears').value) || 10,
          monthly: parseFloat($('gpMonthly').value) || 0,
          lumpsum: parseFloat($('gpLumpsum').value) || 0,
          expected_return: parseFloat($('gpReturn').value) || 12,
        }),
      });
      let lines = '';
      if (d.required_monthly !== undefined) {
        lines = `
          <div class="gp-big">₹${Math.round(d.required_monthly).toLocaleString('en-IN')}<span class="muted" style="font-size:13px">/month SIP</span></div>
          <div class="gp-line">…or invest <b>₹${Math.round(d.lumpsum_needed || 0).toLocaleString('en-IN')}</b> as one lumpsum today.</div>`;
      } else {
        lines = `
          <div class="gp-big ${d.surplus > 0 ? 'up' : 'down'}">₹${Math.round(d.projected).toLocaleString('en-IN')}</div>
          <div class="gp-line">You invest ₹${Math.round(d.invested).toLocaleString('en-IN')}${d.surplus > 0 ? ` · <b class="up">+₹${Math.round(d.surplus).toLocaleString('en-IN')} extra</b>` : ` · <b class="down">shortfall ₹${Math.round(d.shortfall).toLocaleString('en-IN')}</b>`}</div>`;
      }
      const funds = (d.suggested_funds || []).map((f) => `<div class="alloc-picks">• ${esc(f.name)} (${esc(f.category)})</div>`).join('');
      box.innerHTML = `
        <div class="gp-head">To reach ₹${Math.round(d.target).toLocaleString('en-IN')} in ${d.years} yrs @ ${d.expected_return}%</div>
        ${lines}
        <div class="adv-sec"><div class="k">Suggested fund categories: ${esc((d.suggested_categories || []).join(', '))}</div>${funds}</div>`;
    } catch (e) {
      box.innerHTML = `<div class="stitle down">Failed: ${esc(e.message)}</div>`;
    }
  });
}

/* ---------- trading journal ---------- */
let jtSel = null;
function setupJournal() {
  attachAssetSearch($('jtSearch'), (r) => {
    jtSel = r;
    $('jtSelected').classList.remove('hidden');
    $('jtSelected').innerHTML = `Logging: <b>${esc(r.name)}</b> <span class="chip">${esc(r.ticker || r.symbol)} · ${r.currency === 'INR' ? '₹' : '$'}</span>`;
    $('jtAdd').disabled = false;
  });
  $('jtAdd').addEventListener('click', async () => {
    if (!jtSel) return;
    const qty = parseFloat($('jtQty').value);
    const price = parseFloat($('jtPrice').value);
    if (!(qty > 0) || !(price > 0)) { showJtMsg('Enter valid qty and price.', 'err'); return; }
    try {
      const d = await getJSON('/api/journal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          side: $('jtSide').value, symbol: jtSel.symbol, name: jtSel.name,
          qty, price, currency: jtSel.currency || 'INR',
          fees: parseFloat($('jtFees').value) || 0,
          date: $('jtDate').value || new Date().toISOString().slice(0, 10),
        }),
      });
      renderJournal(d);
      $('jtQty').value = ''; $('jtPrice').value = ''; $('jtFees').value = '0';
      showJtMsg('Trade logged ✓', 'ok');
    } catch (e) { showJtMsg(e.message, 'err'); }
  });
}

function showJtMsg(t, kind) {
  const m = $('jtMsg');
  m.textContent = t; m.className = 'msg ' + (kind || 'ok'); m.classList.remove('hidden');
  setTimeout(() => m.classList.add('hidden'), 3500);
}

function renderJournal(d) {
  state.journal = d;
  const stats = $('journalStats');
  const pnl = d.total_pnl || 0;
  const cur = Object.keys(d.by_currency || {}).join(' / ');
  stats.innerHTML = `
    <div class="js-card"><div class="k">Realized P&L (${esc(cur || '—')})</div><div class="v ${updown(pnl)}">${pnl >= 0 ? '+' : ''}${Math.round(pnl).toLocaleString('en-IN')}</div></div>
    <div class="js-card"><div class="k">Win rate</div><div class="v">${d.win_rate != null ? d.win_rate + '%' : '—'}</div></div>
    <div class="js-card"><div class="k">Closed trades</div><div class="v">${d.n_closed} (${d.wins}W / ${d.losses}L)</div></div>
    <div class="js-card"><div class="k">Avg win / loss</div><div class="v" style="font-size:13px"><span class="up">${d.avg_win != null ? '+' + Math.round(d.avg_win) : '—'}</span> / <span class="down">${d.avg_loss != null ? Math.round(d.avg_loss) : '—'}</span></div></div>`;

  const body = $('journalBody');
  const trades = (d.trades || []).slice().reverse();
  if (!trades.length) {
    body.innerHTML = '<tr><td colspan="7" class="empty">No trades logged yet.</td></tr>';
  } else {
    body.innerHTML = '';
    trades.forEach((t) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${esc(t.date)}</td>
        <td><span class="sig-badge ${t.side === 'buy' ? 'buy' : 'sell'}">${t.side.toUpperCase()}</span></td>
        <td><div class="aname">${esc(t.name)}</div><div class="asym">${esc(t.symbol)} · ${t.currency === 'INR' ? '₹' : '$'}</div></td>
        <td class="num">${Number(t.qty).toLocaleString('en-IN')}</td>
        <td class="num">${Number(t.price).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
        <td class="num">${Number(t.fees || 0).toLocaleString('en-IN')}</td>
        <td><button class="xbtn" title="Delete">✕</button></td>`;
      tr.querySelector('.xbtn').addEventListener('click', async () => {
        try { renderJournal(await getJSON('/api/journal/' + t.id, { method: 'DELETE' })); } catch (e) {}
      });
      body.appendChild(tr);
    });
  }

  // open positions + closed trades
  const closed = $('journalClosed');
  let openHtml = '';
  if (d.open_positions && d.open_positions.length) {
    openHtml = `<div class="signals-head" style="margin-top:16px"><h2 style="font-size:14px">📂 Open positions</h2></div>
      <table class="jc-table"><tr><th>Asset</th><th>Qty</th><th>Avg cost</th><th>Invested</th></tr>
      ${d.open_positions.map((p) => `<tr><td><b>${esc(p.name)}</b></td><td>${p.qty}</td><td>${p.avg_cost}</td><td>${Math.round(p.invested).toLocaleString('en-IN')} (${p.currency})</td></tr>`).join('')}</table>`;
  }
  let closedHtml = '';
  if (d.closed && d.closed.length) {
    closedHtml = `<div class="signals-head" style="margin-top:16px"><h2 style="font-size:14px">✅ Closed trades (realized)</h2></div>
      <table class="jc-table"><tr><th>Asset</th><th>Qty</th><th>Buy</th><th>Sell</th><th>P&L</th></tr>
      ${d.closed.map((c) => `<tr><td><b>${esc(c.name)}</b></td><td>${c.qty}</td><td>${c.buy_price}</td><td>${c.sell_price}</td><td class="${updown(c.pnl)}"><b>${c.pnl > 0 ? '+' : ''}${Math.round(c.pnl).toLocaleString('en-IN')}</b> (${c.currency})</td></tr>`).join('')}</table>`;
  }
  closed.innerHTML = openHtml + closedHtml;
}

async function loadJournal() {
  try {
    renderJournal(await getJSON('/api/journal'));
  } catch (e) { /* silent */ }
}

/* ---------- settings (email) ---------- */
function setupSettings() {
  $('settingsBtn').addEventListener('click', async () => {
    $('settingsModal').classList.remove('hidden');
    try {
      const d = await getJSON('/api/settings');
      const s = d.settings;
      $('sEmailEnabled').checked = !!s.email_enabled;
      $('sHost').value = s.smtp_host || '';
      $('sPort').value = s.smtp_port || 587;
      $('sUser').value = s.smtp_user || '';
      $('sTo').value = s.to_addr || '';
      $('sPass').value = '';
      $('sPass').placeholder = s.smtp_pass_set ? 'Saved — leave blank to keep' : 'App password';
      $('sDailyEmail').checked = !!s.daily_email_enabled;
      $('sDailyTime').value = s.daily_email_time || '08:00';
      $('sTwelve').value = s.twelve_data_key || '';
      $('sFinnhub').value = s.finnhub_key || '';
      $('sAlpha').value = s.alpha_vantage_key || '';
      $('sZerodhaEnabled').checked = !!s.zerodha_enabled;
      $('sZKey').value = s.zerodha_api_key || '';
      $('sZSecret').value = '';
      $('sZSecret').placeholder = s.zerodha_api_secret_set ? 'Saved — leave blank to keep' : '••••••••';
      $('sZToken').value = '';
      $('sZToken').placeholder = s.zerodha_access_token_set ? 'Saved — leave blank to keep' : '••••••••';
      $('sTelegramEnabled').checked = !!s.telegram_enabled;
      $('sTelegramToken').value = s.telegram_bot_token || '';
      $('sTelegramChat').value = s.telegram_chat_id || '';
      $('sTelegramDaily').checked = !!s.telegram_daily_enabled;
      $('sAngelEnabled').checked = !!s.angel_enabled;
      $('sAngelClient').value = s.angel_client_code || '';
      $('sAngelKey').value = s.angel_api_key || '';
      $('sAngelPass').value = '';
      $('sAngelPass').placeholder = s.angel_password_set ? 'Saved — leave blank to keep' : '••••••••';
      $('sAngelTotp').value = '';
      $('sAngelTotp').placeholder = s.angel_totp_set ? 'Saved — leave blank to keep' : '6-digit code';
      $('sGoogleFin').checked = (s.google_finance_enabled !== false);
      loadZerodhaStatus();
    } catch (e) {}
  });
  $('settingsClose').addEventListener('click', () => $('settingsModal').classList.add('hidden'));
  $('settingsModal').addEventListener('click', (e) => { if (e.target === $('settingsModal')) $('settingsModal').classList.add('hidden'); });

  const msg = (t, ok) => { const m = $('sMsg'); m.textContent = t; m.className = 'msg ' + (ok ? 'ok' : 'err'); m.classList.remove('hidden'); setTimeout(() => m.classList.add('hidden'), 5000); };

  function currentSettingsBody() {
    return {
      email_enabled: $('sEmailEnabled').checked,
      smtp_host: $('sHost').value.trim(),
      smtp_port: parseInt($('sPort').value) || 587,
      smtp_user: $('sUser').value.trim(),
      smtp_pass: $('sPass').value,
      from_addr: $('sUser').value.trim(),
      to_addr: $('sTo').value.trim(),
      daily_email_enabled: $('sDailyEmail').checked,
      daily_email_time: $('sDailyTime').value.trim() || '08:00',
      twelve_data_key: $('sTwelve').value.trim(),
      finnhub_key: $('sFinnhub').value.trim(),
      alpha_vantage_key: $('sAlpha').value.trim(),
      zerodha_enabled: $('sZerodhaEnabled').checked,
      zerodha_api_key: $('sZKey').value.trim(),
      zerodha_api_secret: $('sZSecret').value,
      zerodha_access_token: $('sZToken').value,
      telegram_enabled: $('sTelegramEnabled').checked,
      telegram_bot_token: $('sTelegramToken').value.trim(),
      telegram_chat_id: $('sTelegramChat').value.trim(),
      telegram_daily_enabled: $('sTelegramDaily').checked,
      angel_enabled: $('sAngelEnabled').checked,
      angel_api_key: $('sAngelKey').value.trim(),
      angel_client_code: $('sAngelClient').value.trim(),
      angel_password: $('sAngelPass').value,
      angel_totp: $('sAngelTotp').value,
      google_finance_enabled: $('sGoogleFin').checked,
    };
  }

  async function persistSettings() {
    await getJSON('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentSettingsBody()),
    });
  }

  $('sSave').addEventListener('click', async () => {
    try {
      await persistSettings();
      msg('Settings saved ✓', true);
      loadZerodhaStatus();
    } catch (e) { msg(e.message, false); }
  });

  async function loadZerodhaStatus() {
    try {
      const d = await getJSON('/api/zerodha/status');
      const el = $('zStatus');
      el.classList.remove('hidden');
      if (d.configured) {
        el.className = 'msg ok';
        el.textContent = '✅ Zerodha connected' + (d.positions ? ` · ${d.positions.length} live positions loaded` : '');
      } else if (d.enabled) {
        el.className = 'msg err';
        el.textContent = '⚠️ Zerodha enabled but no valid credentials yet.';
      } else {
        el.classList.add('hidden');
      }
    } catch (e) { /* silent */ }
  }

  const tgMsg = (t, ok) => { const m = $('tgStatus'); m.textContent = t; m.className = 'msg ' + (ok ? 'ok' : 'err'); m.classList.remove('hidden'); setTimeout(() => m.classList.add('hidden'), 6000); };

  $('sTelegramGetId').addEventListener('click', async () => {
    try {
      // save current token first
      await getJSON('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_bot_token: $('sTelegramToken').value.trim() }),
      });
      const d = await getJSON('/api/telegram/chatid');
      if (d.chat_id) {
        $('sTelegramChat').value = d.chat_id;
        tgMsg('Found your chat id ✓ — click Save all', true);
      }
    } catch (e) {
      tgMsg(e.message || 'Could not find chat id. Message your bot first, then retry.', false);
    }
  });

  $('sTelegramTest').addEventListener('click', async () => {
    try {
      await persistSettings();   // save first so the test uses current values
      const d = await getJSON('/api/telegram/test', { method: 'POST' });
      tgMsg(d.ok ? 'Test message sent ✓ Check Telegram!' : 'Failed: ' + d.message, d.ok);
    } catch (e) { tgMsg(e.message, false); }
  });

  const angelMsg = (t, ok) => { const m = $('angelStatus'); m.textContent = t; m.className = 'msg ' + (ok ? 'ok' : 'err'); m.classList.remove('hidden'); setTimeout(() => m.classList.add('hidden'), 8000); };

  $('sAngelTest').addEventListener('click', async () => {
    angelMsg('Connecting to Angel One…', true);
    try {
      await persistSettings();   // save first so the test uses current values
      const d = await getJSON('/api/angel/test');
      angelMsg(d.message, d.ok);
    } catch (e) { angelMsg(e.message || 'Angel One test failed', false); }
  });

  $('sTest').addEventListener('click', async () => {
    // save first so the test uses current values
    await $('sSave').click();
    try {
      const d = await getJSON('/api/settings/test', { method: 'POST' });
      msg(d.ok ? 'Test email sent ✓ Check your inbox!' : 'Failed: ' + d.message, d.ok);
    } catch (e) { msg(e.message, false); }
  });
}

/* ---------- data loading ---------- */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function loadMovers() {
  try {
    state.movers = await getJSON('/api/movers');
    renderMovers();
  } catch (e) {
    $('moversGrid').innerHTML = '<div class="loader">Could not load market data. Refresh to retry.</div>';
  }
}

async function loadWatchlist() {
  try {
    state.watchlist = await getJSON('/api/watchlist');
    state.watchlistItems = state.watchlist.items;
    renderPicks();
  } catch (e) { /* silent */ }
}

function tick() {
  if (state.movers && state.movers.updated_at) {
    const t = new Date(state.movers.updated_at * 1000);
    $('updated').textContent = 'Updated ' + t.toLocaleTimeString();
  }
}

let signalsTries = 0;
async function loadSignals() {
  try {
    const data = await getJSON('/api/signals');
    if (data && data.stocks_in && data.stocks_in.length) {
      signalsTries = 0;
      state.signals = data;
      renderSignals();
      return;
    }
    signalsTries++;
    if (signalsTries > 6) {
      state.signals = { stocks_in: [], crypto: [], stocks_us: [], overview: {} };
      renderSignals();
      return;
    }
    // backend still warming up -> retry shortly
    setTimeout(loadSignals, 5000);
  } catch (e) {
    signalsTries++;
    if (signalsTries > 6) {
      state.signals = { stocks_in: [], crypto: [], stocks_us: [], overview: {}, error: true };
      renderSignals();
      return;
    }
    setTimeout(loadSignals, 5000);
  }
}

async function loadAll() {
  await Promise.all([loadMovers(), loadWatchlist(), loadSignals(), loadFunds(), loadAlerts(), loadScreener(), loadPnlHistory(), loadMarket(), loadPortfolioHealth(), loadJournal()]);
  tick();
}

/* ---------- boot ---------- */
setupTabs();
setupSearch();
setupAlerts();
setupPdf();
setupScreener();
setupTools();
setupSettings();
setupAdvisor();
setupPlanner();
setupJournal();
['sipAmt', 'sipYears'].forEach((id) => $(id).addEventListener('input', renderSipCard));
loadAll();
setInterval(loadMovers, 30000);    // movers every 30 s (live)
setInterval(loadWatchlist, 45000); // watchlist every 45 s
setInterval(loadSignals, 600000);  // signals every 10 min
setInterval(loadFunds, 600000);    // funds every 10 min
setInterval(loadAlerts, 30000);    // alerts every 30 s
setInterval(loadScreener, 1800000); // screener every 30 min
setInterval(loadPnlHistory, 300000); // pnl history every 5 min
setInterval(loadMarket, 30000);     // market mood every 30 s (live)
setInterval(loadPortfolioHealth, 120000); // portfolio health every 2 min
setInterval(loadJournal, 300000);   // journal every 5 min
setInterval(tick, 30000);
