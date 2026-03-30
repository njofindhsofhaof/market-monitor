// ===== CONFIG =====
const API_URL = "./data.json";
let isLoading = false;
let riskChartInstance = null;

const STATUS_MAP = {
  danger:  { cls: "status-badge--danger",  dot: "dot--danger"  },
  warning: { cls: "status-badge--warning", dot: "dot--warning" },
  success: { cls: "status-badge--success", dot: "dot--success" }
};
const CAT_CLASS = {
  "Địa chính trị":     "cat-geo",
  "Dòng tiền tổ chức": "cat-flow",
  "Thị trường":        "cat-market",
  "Vĩ mô":             "cat-macro",
};

// ===== FETCH =====
async function fetchData(forceRefresh = false) {
  if (isLoading) return;
  isLoading = true;
  setLoadingState(true);
  try {
    const resp = await fetch(API_URL + (forceRefresh ? "?t=" + Date.now() : ""));
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    renderAll(json);
    setError(null);
  } catch (err) {
    setError("Không thể tải dữ liệu. Vui lòng thử lại sau.");
    console.error(err);
  } finally {
    isLoading = false;
    setLoadingState(false);
  }
}

function renderAll(data) {
  if (!data || !data.indicators) return;
  window._lastData = data;
  renderTable(data.indicators);
  updateTimestamp(data.last_updated);
  updateSummaryPills(data.indicators);
  if (data.risk) {
    renderGauge(data.risk);
    renderCategoryCards(data.risk);
  }
  renderRiskChart();
}

// ===== GAUGE =====
function renderGauge(risk) {
  const score = risk.score;
  const color = risk.color;
  const L = I18N[currentLang] || I18N['vi'];

  const scoreEl = document.getElementById('risk-score');
  if (scoreEl) {
    scoreEl.textContent = score;
    // Score la SVG text -- set fill color
    const stroke = score <= 35 ? '#22c55e'
                 : score <= 55 ? '#f59e0b'
                 : score <= 75 ? '#ef4444' : '#a78bfa';
    scoreEl.setAttribute('fill', stroke);
  }

  const badgeEl = document.getElementById('risk-level-badge');
  if (badgeEl) {
    badgeEl.textContent = L.risk_levels?.[risk.level] || risk.level;
    badgeEl.className = `risk-level-badge risk-badge-${color}`;
  }

  // Gauge arc: total arc = 390px dasharray
  const fill = document.getElementById('gauge-fill');
  if (fill) {
    const pct = Math.min(score / 100, 1);
    const offset = 390 * (1 - pct);
    const stroke = score <= 35 ? '#22c55e'
                 : score <= 55 ? '#f59e0b'
                 : score <= 75 ? '#ef4444' : '#a78bfa';
    requestAnimationFrame(() => {
      fill.style.strokeDashoffset = offset;
      fill.style.stroke = stroke;
    });
  }

  // Multiplier
  const multRow = document.getElementById('gauge-mult-row');
  const multEl  = document.getElementById('gauge-mult');
  if (multRow && multEl && risk.multiplier !== undefined) {
    const m = risk.multiplier;
    multEl.textContent = `×${m.toFixed(2)}`;
    multEl.style.color = m > 1.3 ? 'var(--color-danger)'
                       : m > 1.1 ? 'var(--color-warning)'
                       : 'var(--color-success)';
    multRow.style.display = 'block';
  }

  // Leads
  const leadsWrap = document.getElementById('risk-leads-wrap');
  const leadsList = document.getElementById('risk-leads-list');
  if (leadsWrap && leadsList) {
    const leads = risk.active_leads || [];
    if (leads.length > 0) {
      const L2 = I18N[currentLang] || I18N['vi'];
      leadsList.innerHTML = leads.map(l => {
        const t = (currentLang === 'en' && L2.leads?.[l]) ? L2.leads[l] : l;
        return `<li>${escapeHtml(t)}</li>`;
      }).join('');
      leadsWrap.style.display = 'block';
    } else {
      leadsWrap.style.display = 'none';
    }
  }

  // Ref table highlight
  document.querySelectorAll('.ref-table tbody tr').forEach((tr, i) => {
    const ranges = [[0,35],[36,55],[56,75],[76,100]];
    const [lo, hi] = ranges[i];
    tr.classList.toggle('active-row', score >= lo && score <= hi);
  });
}

// ===== CATEGORY CARDS =====
function renderCategoryCards(risk) {
  const bd = risk.breakdown || {};
  const scoreColor = v =>
    v >= 70 ? {text:'var(--color-danger)',cls:'danger'}
    : v >= 50 ? {text:'var(--color-warning)',cls:'warning'}
    : v >= 30 ? {text:'var(--color-warning)',cls:'warning'}
    : {text:'var(--color-success)',cls:'success'};

  ['geo','inst','market','macro'].forEach(key => {
    const val = bd[key];
    if (val === undefined) return;
    const el  = document.getElementById(`bd-${key}`);
    const bar = document.getElementById(`bar-${key}`);
    const c   = scoreColor(val);
    if (el) { el.textContent = val.toFixed(1); el.style.color = c.text; }
    if (bar) {
      requestAnimationFrame(() => {
        bar.style.width = val + '%';
        bar.className = `cat-bar-fill ${c.cls}`;
      });
    }
  });
}

// ===== LINE CHART =====
let _fullHist = [];         // cache full history
let _chartPeriod = '24h';   // current period

async function renderRiskChart(period) {
  if (period) _chartPeriod = period;
  try {
    // Fetch history nếu chưa có cache
    if (!_fullHist.length) {
      const resp = await fetch('./risk_history.json?t=' + Date.now());
      if (!resp.ok) return;
      _fullHist = await resp.json();
    }
    if (!_fullHist.length) return;

    // Dùng timestamp của data mới nhất làm gốc, không phải Date.now()
    const latestDate = new Date(_fullHist[_fullHist.length - 1].date);
    const cutoff = {
      '24h':  new Date(latestDate - 24 * 60 * 60 * 1000),
      '7d':   new Date(latestDate - 7  * 24 * 60 * 60 * 1000),
      '30d':  new Date(latestDate - 30 * 24 * 60 * 60 * 1000),
    }[_chartPeriod] || new Date(0);

    const hist = _fullHist.filter(e => new Date(e.date) >= cutoff);
    const displayHist = (() => {
      if (!hist.length) return _fullHist.slice(-24); // fallback
      if (_chartPeriod === '24h') {
        // 1 điểm/giờ — lấy 24 điểm cuối
        return hist.slice(-24);
      } else {
        // 7d / 30d: 1 điểm/ngày — lấy điểm cuối cùng của mỗi ngày
        const byDay = {};
        hist.forEach(e => {
          const day = e.date.slice(0, 10); // "2026-03-30"
          byDay[day] = e; // overwrite → giữ điểm mới nhất của ngày
        });
        const days = Object.values(byDay);
        return _chartPeriod === '7d' ? days.slice(-7) : days.slice(-30);
      }
    })();

    const canvas = document.getElementById('risk-chart');
    if (!canvas) return;

    const labels = displayHist.map(e => {
      const d = new Date(e.date);
      if (_chartPeriod === '24h') {
        return `${String(d.getHours()).padStart(2,'0')}:00`;
      }
      return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}`;
    });
    const scores    = displayHist.map(e => e.score);
    const ptColors  = scores.map(s => s<=35?'#22c55e':s<=55?'#f59e0b':s<=75?'#ef4444':'#a78bfa');

    const isDark    = document.documentElement.getAttribute('data-theme') !== 'light';
    const gridColor = isDark ? 'rgba(255,255,255,.04)' : 'rgba(0,0,0,.06)';
    const labelColor= isDark ? '#555' : '#aaa';

    if (riskChartInstance) riskChartInstance.destroy();

    const latestScore = scores[scores.length - 1] || 0;
    const lineColor   = latestScore<=35?'#22c55e':latestScore<=55?'#f59e0b':latestScore<=75?'#ef4444':'#a78bfa';

    const r = parseInt(lineColor.slice(1,3),16)||239,
          g = parseInt(lineColor.slice(3,5),16)||68,
          b = parseInt(lineColor.slice(5,7),16)||68;

    riskChartInstance = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: scores,
          borderColor: lineColor,
          borderWidth: 2,
          pointBackgroundColor: ptColors,
          pointBorderColor: ptColors,
          pointRadius: scores.length > 48 ? 2 : 4,
          pointHoverRadius: 6,
          fill: true,
          backgroundColor: (ctx) => {
            const grad = ctx.chart.ctx.createLinearGradient(0,0,0,ctx.chart.height);
            grad.addColorStop(0, `rgba(${r},${g},${b},.2)`);
            grad.addColorStop(1, `rgba(${r},${g},${b},.01)`);
            return grad;
          },
          tension: 0.35,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: isDark ? '#1a1a1a' : '#fff',
            borderColor:     isDark ? '#2e2e2e' : '#e5e5e5',
            borderWidth: 1,
            titleColor: isDark ? '#888' : '#666',
            bodyColor:  isDark ? '#e8e8e8' : '#111',
            callbacks: { label: ctx => ` ${ctx.raw}/100 — ${displayHist[ctx.dataIndex]?.level || ''}` }
          }
        },
        scales: {
          x: { grid:{color:gridColor}, ticks:{color:labelColor,font:{family:'IBM Plex Mono',size:10},maxRotation:0,maxTicksLimit:10} },
          y: { min:0,max:100, grid:{color:gridColor}, ticks:{color:labelColor,font:{family:'IBM Plex Mono',size:10},stepSize:25} }
        }
      }
    });
  } catch(e) { console.warn('Chart error:', e); }
}

// ===== CHART PERIOD TOGGLE =====
function initChartToggle() {
  document.querySelectorAll('.chart-period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.chart-period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _fullHist = []; // force refetch khi đổi period
      renderRiskChart(btn.dataset.period);
    });
  });
}

// ===== TABLE =====
function renderTable(indicators) {
  const tbody = document.getElementById("table-body");
  const L = I18N[currentLang] || I18N["vi"];
  let html = "";

  indicators.forEach((row, idx) => {
    const sm = STATUS_MAP[row.status] || STATUS_MAP.success;
    const isGroupStart = row.category !== "" && idx !== 0;
    const catName     = L.categories?.[row.category] || row.category;
    const indName     = L.indicators?.[row.indicator] || row.indicator;
    const statusLabel = L.status?.[row.statusLabel]   || row.statusLabel;
    const catCls      = CAT_CLASS[row.category] || '';

    let displayValue     = row.value     || "";
    let displayThreshold = row.threshold || "";
    if (currentLang === "en" && L.value_replace) {
      for (const [vi, en] of L.value_replace) {
        displayValue     = displayValue.replace(vi, en);
        displayThreshold = displayThreshold.replace(vi, en);
      }
    }
    if (currentLang === "en" && L.thresholds) {
      displayThreshold = L.thresholds[row.threshold] || displayThreshold;
    }

    const categoryCell = row.category
      ? `<td><span class="category-badge ${catCls}">${escapeHtml(catName)}</span></td>`
      : `<td></td>`;
    const sourceTag = row.link
      ? `<a href="${escapeHtml(row.link)}" target="_blank" rel="noopener" class="source-link">${escapeHtml(row.source||'')}</a>`
      : row.source ? `<span class="source-link">${escapeHtml(row.source)}</span>` : '';

    const trend    = row.trend || "—";
    const trendRaw = row.trend_raw;
    let trendClass = "trend-na";
    if (trend !== "—" && trend !== "N/A" && trendRaw !== null && trendRaw !== undefined) {
      trendClass = trendRaw > 0.05 ? "trend-up" : trendRaw < -0.05 ? "trend-down" : "trend-flat";
    }

    html += `<tr class="${isGroupStart?'group-start':''}" style="--i:${idx}">
      ${categoryCell}
      <td><span class="indicator-name">${escapeHtml(indName)}</span>${sourceTag}</td>
      <td class="td-value">${escapeHtml(displayValue)}</td>
      <td><span class="${trendClass}">${escapeHtml(trend)}</span></td>
      <td class="td-threshold">${escapeHtml(displayThreshold)}</td>
      <td><span class="status-badge ${sm.cls}"><span class="status-dot ${sm.dot}"></span>${escapeHtml(statusLabel)}</span></td>
    </tr>`;
  });

  tbody.innerHTML = html;
}

// ===== PILLS =====
function updateSummaryPills(indicators) {
  const counts = {danger:0,warning:0,success:0};
  indicators.forEach(r => counts[r.status]++);
  document.getElementById("count-canh-bao").textContent    = t("pill_danger",  counts.danger);
  document.getElementById("count-canh-giac").textContent   = t("pill_warning", counts.warning);
  document.getElementById("count-binh-thuong").textContent = t("pill_success", counts.success);
}

function updateTimestamp(lastUpdated) {
  const el = document.getElementById("last-updated");
  if (el) el.textContent = lastUpdated || "N/A";
}

// ===== LOADING =====
function setLoadingState(loading) {
  const btn     = document.getElementById("refresh-btn");
  const spinner = document.getElementById("refresh-spinner");
  if (btn) btn.disabled = loading;
  if (spinner) spinner.style.display = loading ? "inline-block" : "none";
  if (loading) {
    document.querySelectorAll(".td-value,.td-threshold").forEach(td=>td.classList.add("skeleton"));
  } else {
    document.querySelectorAll(".skeleton").forEach(el=>el.classList.remove("skeleton"));
  }
}

function setError(msg) {
  const el = document.getElementById("error-banner");
  if (!el) return;
  if (msg) { el.textContent = "⚠ " + msg; el.style.display = "block"; }
  else      { el.style.display = "none"; }
}

// ===== THEME =====
function initTheme() {
  const toggle = document.querySelector("[data-theme-toggle]");
  const root   = document.documentElement;
  let isDark   = true;
  function setTheme(dark) {
    isDark = dark;
    root.setAttribute("data-theme", dark ? "dark" : "light");
    if (toggle) {
      toggle.innerHTML = dark
        ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`
        : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
    if (riskChartInstance) renderRiskChart();
  }
  setTheme(isDark);
  toggle && toggle.addEventListener("click", ()=>setTheme(!isDark));
}

// ===== UTILS =====
function escapeHtml(str) {
  if (str===null||str===undefined) return "N/A";
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ===== INIT =====
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  setLang(currentLang);
  initChartToggle();
  const langBtn = document.getElementById("lang-toggle");
  langBtn && langBtn.addEventListener("click", ()=>setLang(currentLang==="vi"?"en":"vi"));
  fetchData();
  const refreshBtn = document.getElementById("refresh-btn");
  refreshBtn && refreshBtn.addEventListener("click", ()=>fetchData(true));
});
