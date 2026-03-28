// ===== CONFIG =====
// Vercel: đọc data.json tĩnh (GitHub Actions cập nhật mỗi giờ)
const API_URL     = "./data.json";
const REFRESH_URL = "./data.json"; // không có backend, refresh chỉ đọc lại file

// ===== STATUS MAP =====
const STATUS_MAP = {
  danger:  { cls: "status-badge--danger",  dot: "dot--danger"  },
  warning: { cls: "status-badge--warning", dot: "dot--warning" },
  success: { cls: "status-badge--success", dot: "dot--success" }
};

// ===== STATE =====
let isLoading = false;

// ===== FETCH DATA =====
async function fetchData(forceRefresh = false) {
  if (isLoading) return;
  isLoading = true;
  setLoadingState(true);

  try {
    const url = forceRefresh ? REFRESH_URL : API_URL;
    const resp = await fetch(url);
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
  renderTable(data.indicators);
  updateTimestamp(data.last_updated, data.cache_age_minutes);
  updateSummaryPills(data.indicators);
}

// ===== RENDER TABLE =====
function renderTable(indicators) {
  const tbody = document.getElementById("table-body");
  let html = "";

  indicators.forEach((row, idx) => {
    const sm = STATUS_MAP[row.status] || STATUS_MAP.success;
    const isGroupStart = row.category !== "" && idx !== 0;

    const categoryCell = row.category
      ? `<td class="td-category">
           <span class="category-badge">${escapeHtml(row.category)}</span>
         </td>`
      : `<td class="td-category" aria-hidden="true"></td>`;

    // Source tag with link
    const sourceTag = row.source
      ? (row.link
          ? `<a href="${escapeHtml(row.link)}" target="_blank" rel="noopener" class="source-link">${escapeHtml(row.source)}</a>`
          : `<span class="source-tag">${escapeHtml(row.source)}</span>`)
      : "";

    // Trend cell
    const trend = row.trend || "—";
    const trendRaw = row.trend_raw;
    let trendClass = "trend-na";
    if (trend === "—" || trend === "N/A") {
      trendClass = "trend-na";
    } else if (trendRaw !== null && trendRaw !== undefined) {
      trendClass = trendRaw > 0.05 ? "trend-up" : trendRaw < -0.05 ? "trend-down" : "trend-flat";
    }

    html += `
      <tr class="${isGroupStart ? "group-start" : ""}">
        ${categoryCell}
        <td class="td-indicator">
          <span class="indicator-name">${escapeHtml(row.indicator)}</span>
          ${sourceTag}
        </td>
        <td class="td-value">${escapeHtml(row.value)}</td>
        <td class="td-trend"><span class="${trendClass}">${escapeHtml(trend)}</span></td>
        <td class="td-threshold">${escapeHtml(row.threshold)}</td>
        <td class="td-status">
          <span class="status-badge ${sm.cls}">
            <span class="status-dot ${sm.dot}" aria-hidden="true"></span>
            ${escapeHtml(row.statusLabel)}
          </span>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;

  // Animate rows in
  requestAnimationFrame(() => {
    document.querySelectorAll("#table-body tr").forEach((tr, i) => {
      tr.style.opacity = "0";
      tr.style.transform = "translateY(6px)";
      setTimeout(() => {
        tr.style.transition = "opacity 220ms ease, transform 220ms ease";
        tr.style.opacity = "1";
        tr.style.transform = "translateY(0)";
      }, i * 40);
    });
  });
}

// ===== SUMMARY PILLS =====
function updateSummaryPills(indicators) {
  const counts = { danger: 0, warning: 0, success: 0 };
  indicators.forEach(r => counts[r.status]++);
  document.getElementById("count-canh-bao").textContent     = `${counts.danger} Cảnh báo`;
  document.getElementById("count-canh-giac").textContent    = `${counts.warning} Cảnh giác`;
  document.getElementById("count-binh-thuong").textContent  = `${counts.success} Bình thường`;
}

// ===== TIMESTAMP =====
function updateTimestamp(lastUpdated, cacheAgeMinutes) {
  const el = document.getElementById("last-updated");
  if (lastUpdated) {
    let ageText = "";
    if (cacheAgeMinutes !== undefined && cacheAgeMinutes !== null) {
      if (cacheAgeMinutes < 1) ageText = " (vừa cập nhật)";
      else ageText = ` (${Math.floor(cacheAgeMinutes)} phút trước)`;
    }
    el.textContent = lastUpdated + ageText;
  } else {
    el.textContent = "Đang tải...";
  }
}

// ===== LOADING STATE =====
function setLoadingState(loading) {
  const btn = document.getElementById("refresh-btn");
  const spinner = document.getElementById("refresh-spinner");
  if (btn) btn.disabled = loading;
  if (spinner) spinner.style.display = loading ? "inline-block" : "none";

  if (loading) {
    document.querySelectorAll(".td-value, .td-threshold").forEach(td => {
      td.classList.add("skeleton");
    });
  } else {
    document.querySelectorAll(".skeleton").forEach(el => el.classList.remove("skeleton"));
  }
}

// ===== ERROR STATE =====
function setError(msg) {
  const el = document.getElementById("error-banner");
  if (!el) return;
  if (msg) {
    el.textContent = "⚠ " + msg;
    el.style.display = "block";
  } else {
    el.style.display = "none";
  }
}

// ===== THEME TOGGLE =====
function initTheme() {
  const toggle = document.querySelector("[data-theme-toggle]");
  const root = document.documentElement;
  let isDark = matchMedia("(prefers-color-scheme: dark)").matches;

  function setTheme(dark) {
    isDark = dark;
    root.setAttribute("data-theme", dark ? "dark" : "light");
    toggle && toggle.setAttribute("aria-label", dark ? "Chuyển chế độ sáng" : "Chuyển chế độ tối");
    if (toggle) {
      toggle.innerHTML = dark
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
  }

  setTheme(isDark);
  toggle && toggle.addEventListener("click", () => setTheme(!isDark));
}

// ===== UTILS =====
function escapeHtml(str) {
  if (str === null || str === undefined) return "N/A";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ===== INIT =====
document.addEventListener("DOMContentLoaded", () => {
  initTheme();

  // Fetch data on load
  fetchData();

  // Refresh button
  const refreshBtn = document.getElementById("refresh-btn");
  refreshBtn && refreshBtn.addEventListener("click", () => fetchData(true));
});
