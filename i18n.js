// ===== INTERNATIONALIZATION (i18n) =====
// Mặc định: 'vi' (tiếng Việt)

const I18N = {
  vi: {
    // Header
    page_title:       "Bảng Tổng Hợp Theo Dõi Hàng Ngày",
    page_subtitle_pre: "Cập nhật lần cuối:",
    page_source:      "Nguồn: Yahoo Finance · FRED",
    btn_refresh:      "Refresh",

    // Summary pills
    pill_danger:   (n) => `${n} Cảnh báo`,
    pill_warning:  (n) => `${n} Cảnh giác`,
    pill_success:  (n) => `${n} Bình thường`,

    // Risk card
    risk_title:       "TỔNG ĐIỂM RỦI RO",
    risk_history_label: "Lịch sử điểm (30 ngày gần nhất)",
    bd_geo:    "Địa chính trị",
    bd_market: "Thị trường",
    bd_macro:  "Vĩ mô",
    bd_geo_w:    "(30%)",
    bd_market_w: "(50%)",
    bd_macro_w:  "(20%)",

    // Risk table
    risk_th_range:  "Mức điểm",
    risk_th_meaning:"Ý nghĩa",
    risk_th_action: "Hành động",
    risk_rows: [
      { range: "0–30",   level: "BÌNH THƯỜNG",     action: "Duy trì tỷ trọng, theo dõi định kỳ" },
      { range: "31–50",  level: "CẢNH GIÁC",        action: "Giảm đòn bẩy, chuẩn bị phòng vệ" },
      { range: "51–70",  level: "CẢNH BÁO CAO",     action: "Giảm tỷ trọng rủi ro, tăng tiền mặt & hedge" },
      { range: "71–100", level: "RỦI RO HỆ THỐNG",  action: "Hedge mạnh, chuyển danh mục phòng thủ toàn phần" },
    ],

    // Table headers
    th_category:  "Hạng mục",
    th_indicator: "Chỉ báo",
    th_value:     "Giá trị hiện tại",
    th_trend:     "Xu hướng 1 tuần",
    th_threshold: "Ngưỡng cảnh báo",
    th_status:    "Trạng thái",

    // Loading / error
    loading_text: "Đang tải dữ liệu thị trường...",
    error_text:   "Không thể tải dữ liệu. Vui lòng thử lại sau.",

    // Legend
    legend_title: "CHÚ THÍCH TRẠNG THÁI",
    legend_items: [
      { label: "CẢNH BÁO",    desc: "Chỉ số đã vượt ngưỡng nguy hiểm. Cần theo dõi sát và cân nhắc điều chỉnh danh mục." },
      { label: "CẢNH GIÁC",   desc: "Chỉ số đang tiệm cận ngưỡng cảnh báo. Cần chú ý theo dõi thêm." },
      { label: "BÌNH THƯỜNG", desc: "Chỉ số trong vùng an toàn. Tiếp tục quan sát định kỳ." },
    ],
    source_label: "Nguồn dữ liệu",
    source_desc:  "Yahoo Finance (WTI, VIX, HYG, TLT, TNX, SPY options) · FRED St. Louis Fed (DGS2, DGS10) · Xung đột Hormuz cập nhật thủ công.",
    contact_text: "Mọi ý kiến đóng góp xin liên hệ:",
    contact_thanks: ", cảm ơn bạn.",

    // Status labels (from data.json)
    status: {
      "CẢNH BÁO":   "CẢNH BÁO",
      "CẢNH GIÁC":  "CẢNH GIÁC",
      "Bình thường":"Bình thường",
    },
    risk_levels: {
      "BÌNH THƯỜNG":    "BÌNH THƯỜNG",
      "CẢNH GIÁC":      "CẢNH GIÁC",
      "CẢNH BÁO CAO":   "CẢNH BÁO CAO",
      "RỦI RO HỆ THỐNG":"RỦI RO HỆ THỐNG",
    },

    // Indicator names
    indicators: {
      "Dầu WTI":           "Dầu WTI",
      "Xung đột Hormuz":   "Xung đột Hormuz",
      "VIX":               "VIX",
      "VIX futures curve": "VIX futures curve",
      "HYG/TLT ratio":     "HYG/TLT ratio",
      "Put/Call ratio":    "Put/Call ratio",
      "10-year yield":     "10-year yield",
      "2s10s spread":      "2s10s spread",
    },
    categories: {
      "Địa chính trị": "Địa chính trị",
      "Thị trường":    "Thị trường",
      "Vĩ mô":         "Vĩ mô",
    },
  },

  en: {
    // Header
    page_title:       "Daily Market Monitor",
    page_subtitle_pre: "Last updated:",
    page_source:      "Source: Yahoo Finance · FRED",
    btn_refresh:      "Refresh",

    // Summary pills
    pill_danger:   (n) => `${n} Alert`,
    pill_warning:  (n) => `${n} Caution`,
    pill_success:  (n) => `${n} Normal`,

    // Risk card
    risk_title:       "TOTAL RISK SCORE",
    risk_history_label: "Score history (last 30 days)",
    bd_geo:    "Geopolitical",
    bd_market: "Market",
    bd_macro:  "Macro",
    bd_geo_w:    "(30%)",
    bd_market_w: "(50%)",
    bd_macro_w:  "(20%)",

    // Risk table
    risk_th_range:  "Score range",
    risk_th_meaning:"Meaning",
    risk_th_action: "Action",
    risk_rows: [
      { range: "0–30",   level: "NORMAL",          action: "Maintain allocation, monitor regularly" },
      { range: "31–50",  level: "CAUTION",          action: "Reduce leverage, prepare hedges" },
      { range: "51–70",  level: "HIGH ALERT",       action: "Reduce risk exposure, increase cash & hedge" },
      { range: "71–100", level: "SYSTEMIC RISK",    action: "Activate full hedge, shift to defensive portfolio" },
    ],

    // Table headers
    th_category:  "Category",
    th_indicator: "Indicator",
    th_value:     "Current value",
    th_trend:     "1-week trend",
    th_threshold: "Alert threshold",
    th_status:    "Status",

    // Loading / error
    loading_text: "Loading market data...",
    error_text:   "Failed to load data. Please try again later.",

    // Legend
    legend_title: "STATUS LEGEND",
    legend_items: [
      { label: "ALERT",   desc: "Indicator has breached a danger threshold. Monitor closely and consider portfolio adjustment." },
      { label: "CAUTION", desc: "Indicator is approaching the alert threshold. Keep a close eye on developments." },
      { label: "NORMAL",  desc: "Indicator is within the safe zone. Continue periodic monitoring." },
    ],
    source_label: "Data sources",
    source_desc:  "Yahoo Finance (WTI, VIX, HYG, TLT, TNX, SPY options) · FRED St. Louis Fed (DGS2, DGS10) · Strait of Hormuz updated manually.",
    contact_text: "Feedback & suggestions:",
    contact_thanks: ", thank you.",

    // Status labels
    status: {
      "CẢNH BÁO":   "ALERT",
      "CẢNH GIÁC":  "CAUTION",
      "Bình thường":"Normal",
    },
    risk_levels: {
      "BÌNH THƯỜNG":    "NORMAL",
      "CẢNH GIÁC":      "CAUTION",
      "CẢNH BÁO CAO":   "HIGH ALERT",
      "RỦI RO HỆ THỐNG":"SYSTEMIC RISK",
    },

    // Indicator names
    indicators: {
      "Dầu WTI":           "WTI Crude Oil",
      "Xung đột Hormuz":   "Hormuz Conflict",
      "VIX":               "VIX",
      "VIX futures curve": "VIX futures curve",
      "HYG/TLT ratio":     "HYG/TLT ratio",
      "Put/Call ratio":    "Put/Call ratio",
      "10-year yield":     "10-year yield",
      "2s10s spread":      "2s10s spread",
    },
    categories: {
      "Địa chính trị": "Geopolitical",
      "Thị trường":    "Market",
      "Vĩ mô":         "Macro",
    },
  },
};

// ===== LANGUAGE STATE =====
let currentLang = localStorage.getItem("lang") || "vi";

function setLang(lang) {
  currentLang = lang;
  try { localStorage.setItem("lang", lang); } catch(e) {}
  document.documentElement.setAttribute("lang", lang === "vi" ? "vi" : "en");
  applyLang();
  updateLangToggle();
}

function t(key, ...args) {
  const val = I18N[currentLang]?.[key] ?? I18N["vi"]?.[key];
  return typeof val === "function" ? val(...args) : (val ?? key);
}

function applyLang() {
  const L = I18N[currentLang];
  if (!L) return;

  // Static text elements
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
  const setHTML = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };

  set("page-title",        L.page_title);
  set("page-source-note",  L.page_source);
  set("risk-title",        L.risk_title);
  set("risk-history-label",L.risk_history_label);
  set("bd-geo-label",      `${L.bd_geo} <small>${L.bd_geo_w}</small>`);
  set("bd-market-label",   `${L.bd_market} <small>${L.bd_market_w}</small>`);
  set("bd-macro-label",    `${L.bd_macro} <small>${L.bd_macro_w}</small>`);

  // Use innerHTML for labels with <small>
  const setInner = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };
  setInner("bd-geo-label",    `${L.bd_geo} <small>${L.bd_geo_w}</small>`);
  setInner("bd-market-label", `${L.bd_market} <small>${L.bd_market_w}</small>`);
  setInner("bd-macro-label",  `${L.bd_macro} <small>${L.bd_macro_w}</small>`);

  // Table headers
  set("th-category",  L.th_category);
  set("th-indicator", L.th_indicator);
  set("th-value",     L.th_value);
  set("th-trend",     L.th_trend);
  set("th-threshold", L.th_threshold);
  set("th-status",    L.th_status);

  // Risk table headers
  set("risk-th-range",   L.risk_th_range);
  set("risk-th-meaning", L.risk_th_meaning);
  set("risk-th-action",  L.risk_th_action);

  // Risk table rows
  L.risk_rows.forEach((row, i) => {
    set(`risk-row-level-${i}`, row.level);
    set(`risk-row-action-${i}`, row.action);
  });

  // Legend
  set("legend-title", L.legend_title);
  L.legend_items.forEach((item, i) => {
    set(`legend-label-${i}`, item.label);
    set(`legend-desc-${i}`,  item.desc);
  });
  set("source-label", L.source_label);
  set("source-desc",  L.source_desc);
  set("contact-text", L.contact_text);
  set("contact-thanks", L.contact_thanks);

  // Refresh button label
  const refreshLabel = document.getElementById("refresh-label");
  if (refreshLabel) refreshLabel.textContent = L.btn_refresh;

  // Re-render dynamic content if data is loaded
  if (window._lastData) renderAll(window._lastData);
}

function updateLangToggle() {
  const btn = document.getElementById("lang-toggle");
  if (!btn) return;
  btn.textContent = currentLang === "vi" ? "EN" : "VI";
  btn.setAttribute("title", currentLang === "vi" ? "Switch to English" : "Chuyển sang tiếng Việt");
}
