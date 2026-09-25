/**
 * NEXORA RANGE SCANNER — Frontend Application Controller
 * Handles Navigation, Real-Time WebSocket, Chart Rendering, and Backtest Execution.
 */

let rangeChart = null;
let currentChartSymbol = 'BTCUSDT';
let currentChartTimeframe = '15m';

document.addEventListener('DOMContentLoaded', () => {
  rangeChart = new RangeChart('tv-chart');
  initNavigation();
  initWebSocket();
  loadDashboardData();
  initBacktestForm();
  loadChartData(currentChartSymbol, currentChartTimeframe);

  // Poll status periodically as backup
  setInterval(loadDashboardData, 10000);
});

/* ================= Navigation ================= */
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      const targetTab = item.getAttribute('data-tab');
      document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
      });
      const activePane = document.getElementById(targetTab);
      if (activePane) activePane.classList.add('active');
    });
  });
}

/* ================= WebSocket Real-Time Stream ================= */
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('NEXORA Dashboard: WebSocket connected.');
    document.getElementById('ws-status-text').innerText = 'CONNECTED';
    document.getElementById('ws-status-dot').className = 'dot dot-green';
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'STATUS_UPDATE') {
        updateOverviewMetrics(data.payload);
      } else if (data.type === 'NEW_RANGE') {
        prependRangeRow(data.payload);
      } else if (data.type === 'NEW_SIGNAL') {
        prependSignalRow(data.payload);
      }
    } catch (e) {
      console.error('Error parsing WS message:', e);
    }
  };

  ws.onclose = () => {
    console.warn('NEXORA Dashboard: WebSocket closed. Reconnecting in 3s...');
    document.getElementById('ws-status-text').innerText = 'RECONNECTING';
    document.getElementById('ws-status-dot').className = 'dot dot-amber';
    setTimeout(initWebSocket, 3000);
  };
}

/* ================= Data Loading ================= */
async function loadDashboardData() {
  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const data = await res.json();
      updateOverviewMetrics(data);
    }

    const rangesRes = await fetch('/api/ranges');
    if (rangesRes.ok) {
      const ranges = await rangesRes.json();
      renderRangesTable(ranges);
    }

    const signalsRes = await fetch('/api/signals');
    if (signalsRes.ok) {
      const signals = await signalsRes.json();
      renderSignalsTable(signals);
    }

    const posRes = await fetch('/api/positions');
    if (posRes.ok) {
      const positions = await posRes.json();
      renderPositionsTable(positions);
    }

    const tradesRes = await fetch('/api/trades');
    if (tradesRes.ok) {
      const trades = await tradesRes.json();
      renderTradesTable(trades);
    }
  } catch (err) {
    console.error('Error fetching dashboard data:', err);
  }
}

function updateOverviewMetrics(data) {
  if (data.mode) {
    const modeBadge = document.getElementById('metric-mode');
    if (modeBadge) modeBadge.innerText = data.mode.toUpperCase();
  }
  if (data.balance !== undefined) {
    document.getElementById('metric-balance').innerText = `$${data.balance.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
  }
  if (data.equity !== undefined) {
    document.getElementById('metric-equity').innerText = `$${data.equity.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
  }
  if (data.daily_pnl !== undefined) {
    const el = document.getElementById('metric-daily-pnl');
    el.innerText = `${data.daily_pnl >= 0 ? '+' : ''}$${data.daily_pnl.toFixed(2)}`;
    el.className = `metric-value ${data.daily_pnl >= 0 ? 'text-emerald' : 'text-rose'}`;
  }
  if (data.open_positions_count !== undefined) {
    document.getElementById('metric-open-positions').innerText = data.open_positions_count;
  }
  if (data.active_ranges_count !== undefined) {
    document.getElementById('metric-active-ranges').innerText = data.active_ranges_count;
  }
}

/* ================= Table Renderers ================= */
function renderRangesTable(ranges) {
  const tbody = document.getElementById('ranges-table-body');
  if (!tbody) return;
  if (!ranges || ranges.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#64748b;">No active ranges detected</td></tr>';
    return;
  }

  tbody.innerHTML = ranges.map(r => `
    <tr onclick="loadChartData('${r.symbol}', '${r.timeframe}')" style="cursor:pointer;">
      <td><b>${r.symbol}</b></td>
      <td>${r.timeframe}</td>
      <td>${r.scale_length}</td>
      <td><span class="badge ${r.state === 'CONFIRMED' ? 'badge-confirmed' : (r.state === 'FORMING' ? 'badge-forming' : 'badge-dormant')}">${r.state}</span></td>
      <td>${r.upper.toFixed(4)}</td>
      <td>${r.lower.toFixed(4)}</td>
      <td>${r.band_height_pct.toFixed(2)}%</td>
      <td>${(r.containment * 100).toFixed(1)}%</td>
      <td>${r.held_bars} bars</td>
    </tr>
  `).join('');
}

function renderSignalsTable(signals) {
  const tbody = document.getElementById('signals-table-body');
  if (!tbody) return;
  if (!signals || signals.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#64748b;">No signals generated yet</td></tr>';
    return;
  }

  tbody.innerHTML = signals.map(s => `
    <tr onclick="loadChartData('${s.symbol}', '${s.timeframe}')" style="cursor:pointer;">
      <td><code>${s.signal_id}</code></td>
      <td><b>${s.symbol}</b></td>
      <td><span class="badge ${s.direction.includes('LONG') ? 'badge-long' : 'badge-short'}">${s.direction}</span></td>
      <td>${s.entry_price.toFixed(4)}</td>
      <td>${s.stop_loss.toFixed(4)}</td>
      <td>${s.tp1.toFixed(4)} / ${s.tp2.toFixed(4)}</td>
      <td><span class="badge badge-confirmed">${s.status}</span></td>
    </tr>
  `).join('');
}

function renderPositionsTable(positions) {
  const tbody = document.getElementById('positions-table-body');
  if (!tbody) return;
  if (!positions || positions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#64748b;">No open positions</td></tr>';
    return;
  }

  tbody.innerHTML = positions.map(p => `
    <tr>
      <td><b>${p.symbol}</b></td>
      <td><span class="badge ${p.side === 'BUY' ? 'badge-long' : 'badge-short'}">${p.side}</span></td>
      <td>${p.entry_price.toFixed(4)}</td>
      <td>${p.current_price.toFixed(4)}</td>
      <td>${p.quantity.toFixed(4)}</td>
      <td class="${p.unrealized_pnl >= 0 ? 'text-emerald' : 'text-rose'}"><b>${p.unrealized_pnl >= 0 ? '+' : ''}$${p.unrealized_pnl.toFixed(2)}</b></td>
      <td>${p.stop_loss.toFixed(4)}</td>
      <td>${p.tp1.toFixed(4)}</td>
    </tr>
  `).join('');
}

function renderTradesTable(trades) {
  const tbody = document.getElementById('trades-table-body');
  if (!tbody) return;
  if (!trades || trades.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#64748b;">No closed trades recorded</td></tr>';
    return;
  }

  tbody.innerHTML = trades.map(t => `
    <tr>
      <td><b>${t.symbol}</b></td>
      <td><span class="badge ${t.side === 'BUY' ? 'badge-long' : 'badge-short'}">${t.side}</span></td>
      <td>${t.entry_price.toFixed(4)}</td>
      <td>${t.exit_price.toFixed(4)}</td>
      <td class="${t.net_pnl >= 0 ? 'text-emerald' : 'text-rose'}"><b>${t.net_pnl >= 0 ? '+' : ''}$${t.net_pnl.toFixed(2)}</b></td>
      <td>${t.commission.toFixed(3)} USDT</td>
      <td><span class="badge badge-confirmed">${t.exit_reason}</span></td>
      <td>${new Date(t.closed_at).toLocaleTimeString()}</td>
    </tr>
  `).join('');
}

/* ================= Chart Loader ================= */
async function loadChartData(symbol, timeframe) {
  currentChartSymbol = symbol;
  currentChartTimeframe = timeframe;
  document.getElementById('chart-title').innerText = `${symbol} [${timeframe}] — Auto Range Detector [QuantAlgo]`;

  try {
    const candleRes = await fetch(`/api/candles/${symbol}?timeframe=${timeframe}&limit=120`);
    if (candleRes.ok) {
      const candles = await candleRes.json();
      
      // Fetch latest range for this symbol
      const rangesRes = await fetch(`/api/ranges?symbol=${symbol}`);
      const ranges = rangesRes.ok ? await rangesRes.json() : [];
      const activeRange = ranges.length > 0 ? ranges[0] : null;

      rangeChart.render(candles, activeRange, null);
    }
  } catch (err) {
    console.error('Error loading chart:', err);
  }
}

/* ================= Backtest Runner ================= */
function initBacktestForm() {
  const btn = document.getElementById('btn-run-backtest');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    const symbol = document.getElementById('bt-symbol').value;
    const timeframe = document.getElementById('bt-timeframe').value;
    const limit = document.getElementById('bt-limit').value;

    btn.innerText = 'Running Simulation...';
    btn.disabled = true;

    try {
      const res = await fetch(`/api/backtest/run?symbol=${symbol}&timeframe=${timeframe}&limit=${limit}`, { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        renderBacktestResults(result);
      }
    } catch (e) {
      console.error('Backtest error:', e);
    } finally {
      btn.innerText = 'Run Event-Driven Backtest';
      btn.disabled = false;
    }
  });
}

function renderBacktestResults(res) {
  const m = res.metrics;
  document.getElementById('bt-total-trades').innerText = m.total_trades;
  document.getElementById('bt-win-rate').innerText = `${m.win_rate}%`;
  document.getElementById('bt-profit-factor').innerText = m.profit_factor;
  document.getElementById('bt-net-pnl').innerText = `$${m.net_pnl.toFixed(2)}`;
  document.getElementById('bt-max-dd').innerText = `${m.max_drawdown_pct}%`;
  document.getElementById('bt-sharpe').innerText = m.sharpe_ratio;
  document.getElementById('bt-results-card').style.display = 'block';

  // Render Equity Curve
  if (res.equity_curve && res.equity_curve.length > 0) {
    const trace = {
      x: res.equity_curve.map((_, i) => i),
      y: res.equity_curve,
      type: 'scatter',
      mode: 'lines',
      name: 'Equity Curve',
      line: { color: '#00f2fe', width: 2 }
    };
    const layout = {
      margin: { r: 20, t: 20, b: 30, l: 50 },
      plot_bgcolor: '#0a0d14',
      paper_bgcolor: '#0a0d14',
      xaxis: { title: 'Bar Number', color: '#94a3b8' },
      yaxis: { title: 'Equity (USDT)', color: '#94a3b8' }
    };
    Plotly.newPlot('bt-equity-chart', [trace], layout, { displayModeBar: false, responsive: true });
  }
}
