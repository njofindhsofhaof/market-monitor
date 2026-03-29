// ===== CONFIG =====
const API_URL     = "./data.json";
const REFRESH_URL = "./data.json";

// ===== STATE =====
let isLoading = false;
let riskChartInstance = null;

// ===== STATUS MAP =====
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
    const resp = await fetch(forceRefresh ? REFRESH_URL + "?t=" + Date.now() : API_URL);
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

// ===== RENDER ALL =====
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

  // Score number
  const scoreEl = document.getElementById('risk-score');
  if (scoreEl) {
    scoreEl.textContent = score;
    scoreEl.className = `gauge-score risk-color-${color}`;
  }

  // Badge
  const badgeEl = document.getElementById('risk-level-badge');
  if (badgeEl) {
    badgeEl.textContent = L.risk_levels?.[risk.level] || risk.level;
    badgeEl.className = `risk-level-badge risk-badge-${color}`;
  }

  // Gauge arc fill — semicircle = 283px dasharray
  const fill = document.getElementById('gauge-fill');
  if (fill) {
    const pct = Math.min(score / 100, 1);
    const dashoffset = 283 * (1 - pct);
    // Color by zone
    const strokeColor = score <= 35 ? '#22c55e'
                      : score <= 55 ? '#f59e0b'
                      : score <= 75 ? '#ef4444' : '#a78bfa';
    requestAnimationFrame(() => {
      fill.style.strokeDashoffset = dashoffset;
      fill.style.stroke = strokeColor;
    });
  }

  // Multiplier
  const multRow = document.getElementById('gauge-mult-row');
  const multEl  = document.getElementById('gauge-mult');
  if (multRow && multEl && risk.multiplier !== undefined) {
    const mult = risk.multiplier;
    multEl.textContent = `×${mult.toFixed(2)}`;
    multEl.style.color = mult > 1.3 ? 'var(--color-danger)'
                       : mult > 1.1 ? 'var(--color-warning)'
                       : 'var(--color-success)';
    multRow.style.display = mult !== 1.0 ? 'block' : 'none';
  }

  // Leads
  const leadsWrap = document.getElementById('risk-leads-wrap');
  const leadsList = document.getElementById('risk-leads-list');
  if (leadsWrap && leadsList) {
    const leads = risk.active_leads || [];
    if (leads.length > 0) {
      leadsList.innerHTML = leads.map(l => {
        const translated = (currentLang === 'en' && L.leads?.[l]) ? L.leads[l] : l;
        return `<li>${escapeHtml(translated)}</li>`;
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
  const keys = ['geo','inst','market','macro'];
  const scoreColor = (val) => {
    if (val >= 70) return { text: 'var(--color-danger)',  bar: 'danger' };
    if (val >= 50) return { text: 'var(--color-warning)', bar: 'warning' };
    if (val >= 30) return { text: 'var(--color-warning)', bar: 'warning' };
    return { text: 'var(--color-success)', bar: 'success' };
  };

  keys.forEach(key => {
    const val = bd[key];
    if (val === undefined) return;
    const el  = document.getElementById(`bd-${key}`);
    const bar = document.getElementById(`bar-${key}`);
    const c   = scoreColor(val);
    if (el) {
      el.textContent = val.toFixed(1);
      el.style.color = c.text;
    }
    if (bar) {
      requestAnimationFrame(() => {
        bar.style.width = val + '%';
        bar.className = `cat-bar-fill ${c.bar}`;
      });
    }
  });
}

// ===== LINE CHART =====
async function renderRiskChart() {
  try {
    const resp = await fetch('./risk_history.json?t=' + Date.now());
    if (!resp.ok) return;
    const hist = await resp.json();
    if (!hist.length) return;

    const canvas = document.getElementById('risk-chart');
    if (!canvas) return;

    const labels = hist.map(e => {
      const d = new Date(e.date);
      return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}`;
    });
    const scores = hist.map(e => e.score);

    const pointColors = scores.map(s =>
      s <= 35 ? '#22c55e' : s <= 55 ? '#f59e0b' : s <= 75 ? '#ef4444' : '#a78bfa'
    );

    const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    const gridColor  = isDark ? 'rgba(255,255,255,.05)' : 'rgba(0,0,0,.06)';
    const labelColor = isDark ? '#555' : '#aaa';

    if (riskChartInstance) riskChartInstance.destroy();

    riskChartInstance = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: scores,
          borderColor: '#f59e0b',
          borderWidth: 2,
          pointBackgroundColor: pointColors,
          pointBorderColor: pointColors,
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: true,
          backgroundColor: (ctx) => {
            const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, ctx.chart.height);
            g.addColorStop(0, 'rgba(245,158,11,.18)');
            g.addColorStop(1, 'rgba(245,158,11,.01)');
            return g;
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
            borderColor: isDark ? '#2e2e2e' : '#e5e5e5',
            borderWidth: 1,
            titleColor: isDark ? '#888' : '#666',
            bodyColor: isDark ? '#e8e8e8' : '#111',
            callbacks: {
              label: ctx => ` ${ctx.raw}/100 — ${hist[ctx.dataIndex]?.level || ''}`,
            }
          }
        },
        scales: {
          x: {
            grid: { color: gridColor },
            ticks: { color: labelColor, font: { family: 'IBM Plex Mono', size: 10 }, maxRotation: 0, maxTicksLimit: 10 }
          },
          y: {
            min: 0, max: 100,
            grid: { color: gridColor },
            ticks: { color: labelColor, font: { family: 'IBM Plex Mono', size: 10 }, stepSize: 25 },
            afterDataLimits: (axis) => { axis.min = 0; axis.max = 100; }
          }
        }
      }
    });
  } catch (e) {
    console.warn('Chart error:', e);
  }
}

// ===== TABLE =====
function renderTable(indicators) {
  const tbody = document.getElementById("table-body");
  let html = "";
  const L = I18N[currentLang] || I18N["vi"];

  indicators.forEach((row, idx) => {
    const sm = STATUS_MAP[row.status] || STATUS_MAP.success;
    const isGroupStart = row.category !== "" && idx !== 0;
    const catName = L.categories?.[row.category] || row.category;
    const indName = L.indicators?.[row.indicator] || row.indicator;
    const statusLabel = L.status?.[row.statusLabel] || row.statusLabel;
    const catCls = CAT_CLASS[row.category] || '';

    // Value + threshold translation
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
      ? `<a href="${escapeHtml(row.link)}" target="_blank" rel="noopener" class="source-link">${escapeHtml(row.source || '')}</a>`
      : row.source ? `<span class="source-link">${escapeHtml(row.source)}</span>` : '';

    const trend = row.trend || "—";
    const trendRaw = row.trend_raw;
    let trendClass = "trend-na";
    if (trend !== "—" && trend !== "N/A" && trendRaw !== null && trendRaw !== undefined) {
      trendClass = trendRaw > 0.05 ? "trend-up" : trendRaw < -0.05 ? "trend-down" : "trend-flat";
    }

    html += `<tr class="${isGroupStart ? 'group-start' : ''}" style="--i:${idx}">
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

// ===== SUMMARY PILLS =====
function updateSummaryPills(indicators) {
  const counts = { danger: 0, warning: 0, success: 0 };
  indicators.forEach(r => counts[r.status]++);
  document.getElementById("count-canh-bao").textContent    = t("pill_danger",  counts.danger);
  document.getElementById("count-canh-giac").textContent   = t("pill_warning", counts.warning);
  document.getElementById("count-binh-thuong").textContent = t("pill_success", counts.success);
}

// ===== TIMESTAMP =====
function updateTimestamp(lastUpdated) {
  const el = document.getElementById("last-updated");
  if (el) el.textContent = lastUpdated || "N/A";
}

// ===== LOADING =====
function setLoadingState(loading) {
  const btn = document.getElementById("refresh-btn");
  const spinner = document.getElementById("refresh-spinner");
  if (btn) btn.disabled = loading;
  if (spinner) spinner.style.display = loading ? "inline-block" : "none";
  if (loading) {
    document.querySelectorAll(".td-value, .td-threshold").forEach(td => td.classList.add("skeleton"));
  } else {
    document.querySelectorAll(".skeleton").forEach(el => el.classList.remove("skeleton"));
  }
}

// ===== ERROR =====
function setError(msg) {
  const el = document.getElementById("error-banner");
  if (!el) return;
  if (msg) { el.textContent = "⚠ " + msg; el.style.display = "block"; }
  else { el.style.display = "none"; }
}

// ===== THEME =====
function initTheme() {
  const toggle = document.querySelector("[data-theme-toggle]");
  const root   = document.documentElement;
  let isDark   = true; // default dark

  function setTheme(dark) {
    isDark = dark;
    root.setAttribute("data-theme", dark ? "dark" : "light");
    if (toggle) {
      toggle.innerHTML = dark
        ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`
        : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
    // Redraw chart with new theme colors
    if (riskChartInstance) renderRiskChart();
  }

  setTheme(isDark);
  toggle && toggle.addEventListener("click", () => setTheme(!isDark));
}

// ===== UTILS =====
function escapeHtml(str) {
  if (str === null || str === undefined) return "N/A";
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ===== INIT =====
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  setLang(currentLang);
  const langBtn = document.getElementById("lang-toggle");
  langBtn && langBtn.addEventListener("click", () => setLang(currentLang === "vi" ? "en" : "vi"));
  fetchData();
  const refreshBtn = document.getElementById("refresh-btn");
  refreshBtn && refreshBtn.addEventListener("click", () => fetchData(true));
});
