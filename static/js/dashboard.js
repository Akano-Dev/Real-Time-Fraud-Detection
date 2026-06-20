/**
 * Real-Time Fraud Detection — Dashboard JS
 * Handles live data refresh, Chart.js charts, table rendering, search/filter.
 */

// ─── State ──────────────────────────────────────────────────
const state = {
  activePage:      'dashboard',
  searchQuery:     '',
  riskFilter:      'all',
  lastTxnCount:    0,
  lastFraudCount:  0,
  charts:          {},
  refreshInterval: null,
};

// ─── Page navigation ─────────────────────────────────────────
function showPage(pageId) {
  document.querySelectorAll('.page-content').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-nav a').forEach(a => a.classList.remove('active'));
  const page = document.getElementById('page-' + pageId);
  if (page) page.classList.add('active');
  const link = document.querySelector(`[data-page="${pageId}"]`);
  if (link) link.classList.add('active');
  state.activePage = pageId;
  document.getElementById('header-page-title').textContent = pageTitles[pageId] || 'Dashboard';
  if (pageId === 'analytics') initAnalyticsCharts();
}

const pageTitles = {
  dashboard: 'Live Dashboard',
  analytics: 'Analytics',
  frauds:    'Fraud Alerts',
  reports:   'Reports & Export',
};

// ─── API helpers ─────────────────────────────────────────────
async function apiFetch(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    console.error('API error:', url, e);
    return null;
  }
}

// ─── Stats cards ─────────────────────────────────────────────
async function refreshStats() {
  const data = await apiFetch('/api/stats');
  if (!data) return;

  animateNumber('stat-total',   data.total);
  animateNumber('stat-fraud',   data.fraud);
  animateNumber('stat-legit',   data.legitimate);
  setEl('stat-pct',    data.fraud_percentage.toFixed(2) + '%');
  setEl('stat-avgr',   (data.avg_risk * 100).toFixed(1) + '%');

  // Show fraud banner if new frauds appeared
  if (data.fraud > state.lastFraudCount && state.lastFraudCount > 0) {
    const delta = data.fraud - state.lastFraudCount;
    showToast(`${delta} new fraud alert${delta > 1 ? 's' : ''} detected!`, 'fraud',
              `Fraud count: ${data.fraud} / ${data.total} total`);
  }
  state.lastFraudCount = data.fraud;
  state.lastTxnCount   = data.total;
}

function setEl(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function animateNumber(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const current = parseInt(el.textContent.replace(/,/g, '')) || 0;
  if (current === target) return;
  const step  = Math.ceil(Math.abs(target - current) / 12);
  const sign  = target > current ? 1 : -1;
  let   value = current;
  const tick  = setInterval(() => {
    value += sign * step;
    if ((sign > 0 && value >= target) || (sign < 0 && value <= target)) {
      value = target;
      clearInterval(tick);
    }
    el.textContent = value.toLocaleString();
  }, 40);
}

// ─── Transaction table ────────────────────────────────────────
async function refreshTransactions() {
  const params = new URLSearchParams({ limit: 60 });
  if (state.riskFilter !== 'all') params.set('risk', state.riskFilter);
  if (state.searchQuery)          params.set('search', state.searchQuery);

  const rows = await apiFetch(`/api/transactions?${params}`);
  if (!rows) return;
  renderTable(rows, 'txn-tbody');
}

function renderTable(rows, tbodyId) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;

  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--txt-muted)">
      <i class="fa-solid fa-inbox" style="font-size:28px;display:block;margin-bottom:8px"></i>
      No transactions yet — simulation is running…
    </td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const prob     = (r.fraud_probability * 100).toFixed(1);
    const probFill = fillColor(r.risk_level);
    const amtClass = r.amount > 3000 ? 'amount-high' : r.amount > 500 ? 'amount-med' : 'amount-low';
    return `
    <tr>
      <td><span class="txn-id">${r.transaction_id}</span></td>
      <td class="amount-cell ${amtClass}">$${Number(r.amount).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
      <td><span class="type-chip">${r.txn_type}</span></td>
      <td>${r.location}</td>
      <td>${formatHour(r.hour)}</td>
      <td>
        <span class="badge-risk badge-${r.risk_level}">
          <i class="fa-solid ${riskIcon(r.risk_level)}"></i>
          ${r.risk_level}
        </span>
      </td>
      <td>
        <div class="prob-bar-wrap">
          <div class="prob-bar">
            <div class="prob-fill" style="width:${prob}%;background:${probFill}"></div>
          </div>
          <span class="prob-val">${prob}%</span>
        </div>
      </td>
      <td style="color:var(--txt-muted);font-size:12px">${fmtTime(r.timestamp)}</td>
    </tr>`;
  }).join('');
}

function fillColor(level) {
  return level === 'fraud' ? 'var(--red)' : level === 'suspicious' ? 'var(--yellow)' : 'var(--green)';
}

function riskIcon(level) {
  return level === 'fraud' ? 'fa-skull-crossbones' : level === 'suspicious' ? 'fa-triangle-exclamation' : 'fa-shield-halved';
}

function formatHour(h) {
  const suffix = h >= 12 ? 'PM' : 'AM';
  const hh = h % 12 || 12;
  return `${hh}:00 ${suffix}`;
}

function fmtTime(ts) {
  if (!ts) return '—';
  const d = new Date(ts + (ts.includes('T') ? '' : 'Z'));
  return d.toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
}

// ─── Main dashboard charts ────────────────────────────────────
async function refreshDashboardCharts() {
  const [trends, dist] = await Promise.all([
    apiFetch('/api/charts/trends'),
    apiFetch('/api/charts/distribution'),
  ]);
  if (trends) updateTrendsChart(trends);
  if (dist)   updateDistChart(dist);
}

function initDashboardCharts() {
  // Trend line chart
  state.charts.trends = new Chart(document.getElementById('chart-trends'), {
    type: 'line',
    data: {
      labels:   [],
      datasets: [
        { label: 'Total',  data: [], borderColor: 'rgba(59,130,246,0.8)',   backgroundColor: 'rgba(59,130,246,0.08)', fill: true, tension: 0.4, pointRadius: 2 },
        { label: 'Fraud',  data: [], borderColor: 'rgba(239,68,68,0.9)',    backgroundColor: 'rgba(239,68,68,0.08)',  fill: true, tension: 0.4, pointRadius: 2 },
      ],
    },
    options: chartOptions('Transactions per Minute'),
  });

  // Doughnut distribution chart
  state.charts.dist = new Chart(document.getElementById('chart-dist'), {
    type: 'doughnut',
    data: {
      labels:   ['Safe', 'Suspicious', 'Fraud'],
      datasets: [{ data: [0,0,0], backgroundColor: ['rgba(16,185,129,0.8)','rgba(245,158,11,0.8)','rgba(239,68,68,0.8)'], borderWidth: 2, borderColor: '#111827' }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: '68%',
      plugins: { legend: { position: 'right', labels: { color: '#8898b4', font: { size: 12 }, padding: 16 } } },
    },
  });
}

function updateTrendsChart(data) {
  const c = state.charts.trends;
  if (!c) return;
  c.data.labels              = data.map(d => d.minute);
  c.data.datasets[0].data   = data.map(d => d.total);
  c.data.datasets[1].data   = data.map(d => d.fraud);
  c.update('none');
}

function updateDistChart(data) {
  const c = state.charts.dist;
  if (!c) return;
  const map = { safe: 0, suspicious: 0, fraud: 0 };
  data.forEach(d => { map[d.risk_level] = d.count; });
  c.data.datasets[0].data = [map.safe, map.suspicious, map.fraud];
  c.update('none');
}

// ─── Analytics charts ─────────────────────────────────────────
let analyticsInited = false;
async function initAnalyticsCharts() {
  const [hourly, timeline] = await Promise.all([
    apiFetch('/api/charts/hourly'),
    apiFetch('/api/charts/risk_timeline'),
  ]);

  if (!analyticsInited) {
    analyticsInited = true;

    // Hourly bar chart
    state.charts.hourly = new Chart(document.getElementById('chart-hourly'), {
      type: 'bar',
      data: {
        labels: Array.from({length:24}, (_,i) => `${i}h`),
        datasets: [
          { label: 'Total',      data: Array(24).fill(0), backgroundColor: 'rgba(59,130,246,0.5)',  borderColor: 'rgba(59,130,246,0.8)',  borderWidth:1, borderRadius:4 },
          { label: 'Fraud',      data: Array(24).fill(0), backgroundColor: 'rgba(239,68,68,0.65)', borderColor: 'rgba(239,68,68,0.9)',   borderWidth:1, borderRadius:4 },
        ],
      },
      options: chartOptions('Transactions by Hour of Day', true),
    });

    // Risk timeline area chart
    state.charts.timeline = new Chart(document.getElementById('chart-timeline'), {
      type: 'line',
      data: {
        labels: [],
        datasets: [{ label: 'Fraud Probability', data: [], borderColor: 'rgba(139,92,246,0.9)', backgroundColor: 'rgba(139,92,246,0.12)', fill: true, tension: 0.4, pointRadius: 2 }],
      },
      options: {
        ...chartOptions('Fraud Probability Timeline'),
        scales: {
          x: { ticks: { color: '#8898b4', maxRotation: 45, font:{size:10} }, grid: { color: 'rgba(31,45,69,0.5)' } },
          y: { min: 0, max: 1, ticks: { color: '#8898b4', callback: v => (v*100).toFixed(0)+'%', font:{size:11} }, grid: { color: 'rgba(31,45,69,0.5)' } },
        },
      },
    });
  }

  if (hourly) {
    const c = state.charts.hourly;
    c.data.datasets[0].data = hourly.map(d => d.total);
    c.data.datasets[1].data = hourly.map(d => d.fraud);
    c.update('none');
  }

  if (timeline) {
    const c = state.charts.timeline;
    c.data.labels             = timeline.map(d => d.ts);
    c.data.datasets[0].data   = timeline.map(d => d.fraud_probability);
    c.update('none');
  }
}

// ─── Fraud alerts page ────────────────────────────────────────
async function refreshFraudPage() {
  const data = await apiFetch('/api/frauds');
  if (!data) return;
  renderTable(data, 'fraud-tbody');
  setEl('fraud-count-badge', data.length + ' alerts');
}

// ─── Shared chart options ─────────────────────────────────────
function chartOptions(titleText, stacked = false) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { labels: { color: '#8898b4', font: { size: 12 }, padding: 16, boxWidth: 12 } },
      tooltip: {
        backgroundColor: '#1a2236',
        borderColor: '#1f2d45',
        borderWidth: 1,
        titleColor: '#e8edf5',
        bodyColor: '#8898b4',
        padding: 10,
      },
    },
    scales: {
      x: {
        stacked,
        ticks: { color: '#8898b4', font: { size: 11 }, maxRotation: 0 },
        grid:  { color: 'rgba(31,45,69,0.5)' },
      },
      y: {
        stacked,
        ticks: { color: '#8898b4', font: { size: 11 } },
        grid:  { color: 'rgba(31,45,69,0.5)' },
        beginAtZero: true,
      },
    },
  };
}

// ─── Toast notifications ──────────────────────────────────────
function showToast(title, type = 'safe', message = '') {
  const icons = { fraud: 'fa-skull-crossbones', suspicious: 'fa-triangle-exclamation', safe: 'fa-shield-halved' };
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast-notif ${type}`;
  toast.innerHTML = `
    <i class="toast-icon fa-solid ${icons[type] || icons.safe}"></i>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      ${message ? `<div class="toast-msg">${message}</div>` : ''}
    </div>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('toast-exit');
    setTimeout(() => toast.remove(), 350);
  }, 3500);
}

// ─── CSV export ───────────────────────────────────────────────
function exportCSV() {
  window.location.href = '/api/export';
  showToast('CSV Export Started', 'safe', 'Download will begin shortly.');
}

// ─── Search & filter ──────────────────────────────────────────
function handleSearch(e) {
  state.searchQuery = e.target.value.trim();
  refreshTransactions();
}

function handleFilter(e) {
  state.riskFilter = e.target.value;
  refreshTransactions();
}

// ─── Clock ────────────────────────────────────────────────────
function startClock() {
  const el = document.getElementById('live-clock');
  if (!el) return;
  const tick = () => {
    el.textContent = new Date().toLocaleTimeString('en-US',
      {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  };
  tick();
  setInterval(tick, 1000);
}

// ─── Master refresh ───────────────────────────────────────────
async function masterRefresh() {
  await refreshStats();
  if (state.activePage === 'dashboard') {
    await refreshTransactions();
    await refreshDashboardCharts();
  } else if (state.activePage === 'frauds') {
    await refreshFraudPage();
  } else if (state.activePage === 'analytics') {
    await initAnalyticsCharts();
  }
}

// ─── Bootstrap ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDashboardCharts();
  startClock();
  masterRefresh();
  setInterval(masterRefresh, 3000);   // auto-refresh every 3 s

  // Sidebar navigation
  document.querySelectorAll('.sidebar-nav a[data-page]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      showPage(link.dataset.page);
    });
  });

  // Search
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    let debounce;
    searchInput.addEventListener('input', e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => handleSearch(e), 300);
    });
  }

  // Filter
  const filterSel = document.getElementById('risk-filter');
  if (filterSel) filterSel.addEventListener('change', handleFilter);

  // Export button
  const exportBtn = document.getElementById('export-btn');
  if (exportBtn) exportBtn.addEventListener('click', exportCSV);

  // Start on dashboard
  showPage('dashboard');
  showToast('System Online', 'safe', 'Real-time fraud monitoring is active.');
});
