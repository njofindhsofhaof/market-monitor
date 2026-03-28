"""
Script độc lập: fetch dữ liệu thị trường và ghi ra data.json
Chạy bởi GitHub Actions mỗi giờ.
"""
import json, datetime, os
import yfinance as yf

OUTPUT        = os.path.join(os.path.dirname(__file__), "data.json")
PC_HISTORY    = os.path.join(os.path.dirname(__file__), "pc_history.json")
RISK_HISTORY  = os.path.join(os.path.dirname(__file__), "risk_history.json")

# ===== HELPERS =====

def get_price(symbol):
    try:
        return round(float(yf.Ticker(symbol).fast_info["lastPrice"]), 4)
    except:
        return None

def get_history(symbol, period="10d"):
    try:
        return yf.Ticker(symbol).history(period=period)["Close"]
    except:
        return None

def week_change(hist):
    """% thay đổi so với 5 phiên trước (1 tuần giao dịch)."""
    if hist is None or len(hist) < 2:
        return None
    now = hist.iloc[-1]
    ago = hist.iloc[-6] if len(hist) >= 6 else hist.iloc[0]
    return round((now - ago) / ago * 100, 2)

def fmt_change(chg):
    """Format xu hướng: +1.3% ↑ hoặc -2.1% ↓"""
    if chg is None:
        return "N/A"
    arrow = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
    return f"{chg:+.1f}% {arrow}"

def evaluate(indicator, value):
    if value is None:
        return "success", "Bình thường"
    if indicator == "wti":
        return ("danger","CẢNH BÁO") if value > 95 else ("warning","CẢNH GIÁC") if value > 85 else ("success","Bình thường")
    if indicator == "vix":
        return ("danger","CẢNH BÁO") if value >= 30 else ("warning","CẢNH GIÁC") if value >= 22 else ("success","Bình thường")
    if indicator == "put_call":
        return ("danger","CẢNH BÁO") if value >= 1.1 else ("warning","CẢNH GIÁC") if value >= 0.95 else ("success","Bình thường")
    if indicator == "yield_10y":
        return ("danger","CẢNH BÁO") if value >= 4.5 else ("warning","CẢNH GIÁC") if value >= 4.3 else ("success","Bình thường")
    if indicator == "spread_2s10s":
        return ("danger","CẢNH BÁO") if value < -0.2 else ("warning","CẢNH GIÁC") if value < 0 else ("success","Bình thường")
    if indicator == "hyg_tlt_change":
        return ("danger","CẢNH BÁO") if value <= -5 else ("warning","CẢNH GIÁC") if value <= -3 else ("success","Bình thường")
    return "success", "Bình thường"

# ===== FETCH FUNCTIONS =====

def fetch_wti():
    hist = get_history("CL=F")
    price = get_price("CL=F")
    chg = week_change(hist)
    status, label = evaluate("wti", price)
    return {
        "category": "Địa chính trị",
        "indicator": "Dầu WTI",
        "value": f"${price:.2f}/thùng" if price else "N/A",
        "trend": fmt_change(chg),
        "trend_raw": chg,
        "threshold": ">95 USD/thùng",
        "status": status,
        "statusLabel": label,
        "source": "Yahoo Finance (CL=F)",
        "link": "https://finance.yahoo.com/quote/CL=F/",
        "note": "Giá dầu thô WTI giao ngay (futures front-month)"
    }

def fetch_hormuz():
    """Xung đột Hormuz — không có API, link thẳng đến Reuters search."""
    return {
        "category": "",
        "indicator": "Xung đột Hormuz",
        "value": "Chưa phong tỏa",
        "trend": "—",
        "trend_raw": None,
        "threshold": "Có phong tỏa",
        "status": "success",
        "statusLabel": "Bình thường",
        "source": "Reuters (thủ công)",
        "link": "https://www.reuters.com/search/news?blob=Strait+of+Hormuz",
        "note": "Cập nhật thủ công — bấm link để xem tin mới nhất từ Reuters"
    }

def fetch_vix():
    hist_vix  = get_history("^VIX")
    hist_vixy = get_history("VIXY")   # VIX front-month ETF làm proxy M1
    price = get_price("^VIX")
    vixy  = get_price("VIXY")
    chg = week_change(hist_vix)
    status, label = evaluate("vix", price)
    return {
        "category": "Thị trường",
        "indicator": "VIX",
        "value": f"{price:.2f}" if price else "N/A",
        "trend": fmt_change(chg),
        "trend_raw": chg,
        "threshold": ">30",
        "status": status,
        "statusLabel": label,
        "source": "Yahoo Finance (^VIX)",
        "link": "https://finance.yahoo.com/quote/%5EVIX/",
        "note": "CBOE Volatility Index — chỉ số sợ hãi thị trường"
    }, {
        # VIX Futures Curve
        "category": "",
        "indicator": "VIX futures curve",
        "value": _vix_curve_value(price, vixy),
        "trend": fmt_change(week_change(hist_vixy)),
        "trend_raw": week_change(hist_vixy),
        "threshold": "Backwardation",
        "status": _vix_curve_status(price, vixy)[0],
        "statusLabel": _vix_curve_status(price, vixy)[1],
        "source": "Yahoo Finance (^VIX, VIXY)",
        "link": "https://finance.yahoo.com/quote/VIXY/",
        "note": "So sánh VIX spot vs VIXY ETF (proxy M1 futures)"
    }

def _vix_curve_value(spot, vixy_price):
    """
    VIXY ~= VIX M1 futures / 10 (tương đối).
    So sánh trực tiếp spot vs VIXY*10 để suy ra Contango/Backwardation.
    """
    if spot is None:
        return "N/A"
    if vixy_price:
        m1_proxy = round(vixy_price * 10, 1)  # ước lượng VX M1
        diff = m1_proxy - spot
        if diff > 1:
            return f"Contango nhẹ (spot {spot:.1f} → M1~{m1_proxy:.0f})"
        elif diff < -1:
            return f"Backwardation (spot {spot:.1f} → M1~{m1_proxy:.0f})"
        else:
            return f"Phẳng (spot {spot:.1f} ≈ M1~{m1_proxy:.0f})"
    return f"VIX spot {spot:.1f} (M1 không có dữ liệu)"

def _vix_curve_status(spot, vixy_price):
    if spot is None:
        return "success", "Bình thường"
    if vixy_price:
        m1_proxy = vixy_price * 10
        if m1_proxy < spot - 1:
            return "danger", "CẢNH BÁO"
        elif abs(m1_proxy - spot) <= 1:
            return "warning", "CẢNH GIÁC"
    # VIX spot cao → uncertain
    if spot > 30:
        return "warning", "CẢNH GIÁC"
    return "success", "Bình thường"

def fetch_hyg_tlt():
    hyg_h = get_history("HYG")
    tlt_h = get_history("TLT")
    if hyg_h is None or tlt_h is None or len(hyg_h) < 2 or len(tlt_h) < 2:
        return {
            "category": "", "indicator": "HYG/TLT ratio",
            "value": "Đang theo dõi", "trend": "N/A", "trend_raw": None,
            "threshold": "Giảm >5%/tuần", "status": "success", "statusLabel": "Bình thường",
            "source": "Yahoo Finance (HYG, TLT)",
            "link": "https://finance.yahoo.com/quote/HYG/",
            "note": "Tỷ lệ trái phiếu rủi ro cao / trái phiếu dài hạn"
        }
    r_now = hyg_h.iloc[-1] / tlt_h.iloc[-1]
    r_ago = (hyg_h.iloc[-6] if len(hyg_h)>=6 else hyg_h.iloc[0]) / \
            (tlt_h.iloc[-6] if len(tlt_h)>=6 else tlt_h.iloc[0])
    chg = round((r_now - r_ago) / r_ago * 100, 2)
    status, label = evaluate("hyg_tlt_change", chg)
    return {
        "category": "",
        "indicator": "HYG/TLT ratio",
        "value": f"{r_now:.4f}",
        "trend": fmt_change(chg),
        "trend_raw": chg,
        "threshold": "Giảm >5%/tuần",
        "status": status,
        "statusLabel": label,
        "source": "Yahoo Finance (HYG, TLT)",
        "link": "https://finance.yahoo.com/quote/HYG/",
        "note": "Tỷ lệ trái phiếu rủi ro cao / trái phiếu dài hạn — đo khẩu vị rủi ro"
    }

def _load_pc_history():
    """Đọc lịch sử P/C ratio từ file JSON."""
    if os.path.exists(PC_HISTORY):
        with open(PC_HISTORY, encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_pc_history(ratio):
    """
    Thêm entry mới vào lịch sử, giữ tối đa 10 entries (≈10 giờ).
    Chỉ lưu 1 entry mỗi ngày giao dịch (so sánh theo date).
    """
    hist = _load_pc_history()
    now_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat()
    today = now_str[:10]  # YYYY-MM-DD

    # Nếu đã có entry hôm nay thì cập nhật thay vì append
    if hist and hist[-1]["date"] == today:
        hist[-1]["ratio"] = ratio
    else:
        hist.append({"date": today, "ratio": ratio})

    hist = hist[-10:]  # giữ 10 ngày gần nhất
    with open(PC_HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    return hist

def _pc_week_change(current_ratio):
    """Tính % thay đổi P/C ratio so với 5 ngày trước."""
    hist = _load_pc_history()
    # Tìm entry cũ nhất có thể (≥5 ngày trước)
    if len(hist) >= 2:
        old = hist[0]["ratio"]  # entry cũ nhất trong lịch sử
        chg = round((current_ratio - old) / old * 100, 2)
        days = len(hist) - 1
        return chg, days
    return None, None

def fetch_put_call():
    try:
        spy = yf.Ticker("SPY")
        exp = spy.options[0]
        chain = spy.option_chain(exp)
        c = chain.calls["volume"].sum()
        p = chain.puts["volume"].sum()
        ratio = round(float(p/c), 3) if c > 0 else None

        # Lưu vào lịch sử và tính xu hướng
        trend_str = "—"
        trend_raw = None
        if ratio:
            _save_pc_history(ratio)
            chg, days = _pc_week_change(ratio)
            if chg is not None and days >= 3:
                trend_str = fmt_change(chg)
                trend_raw = chg
            elif chg is not None:
                trend_str = f"{chg:+.1f}% ({days}ngày)"
                trend_raw = chg

        status, label = evaluate("put_call", ratio)
        return {
            "category": "",
            "indicator": "Put/Call ratio",
            "value": f"{ratio:.3f}" if ratio else "N/A",
            "trend": trend_str,
            "trend_raw": trend_raw,
            "threshold": ">1.1",
            "status": status,
            "statusLabel": label,
            "source": "Yahoo Finance (SPY options)",
            "link": "https://finance.yahoo.com/quote/SPY/options/",
            "note": f"SPY options exp {exp} — tỷ lệ put/call đo mức phòng thủ nhà đầu tư"
        }
    except:
        return {
            "category": "", "indicator": "Put/Call ratio",
            "value": "N/A", "trend": "—", "trend_raw": None,
            "threshold": ">1.1", "status": "success", "statusLabel": "Bình thường",
            "source": "Yahoo Finance (SPY options)",
            "link": "https://finance.yahoo.com/quote/SPY/options/",
            "note": "Không lấy được dữ liệu options"
        }

def fetch_yield_10y():
    hist = get_history("^TNX")
    price = get_price("^TNX")
    chg = week_change(hist)
    status, label = evaluate("yield_10y", price)
    return {
        "category": "Vĩ mô",
        "indicator": "10-year yield",
        "value": f"{price:.2f}%" if price else "N/A",
        "trend": fmt_change(chg),
        "trend_raw": chg,
        "threshold": ">4.5%",
        "status": status,
        "statusLabel": label,
        "source": "Yahoo Finance (^TNX)",
        "link": "https://finance.yahoo.com/quote/%5ETNX/",
        "note": "Lợi suất trái phiếu Mỹ 10 năm — ảnh hưởng đến định giá cổ phiếu"
    }

def fetch_spread_2s10s():
    hist_10y = get_history("^TNX")
    hist_2y  = get_history("2YY=F")
    y10 = get_price("^TNX")
    y2  = get_price("2YY=F")

    if y10 and y2:
        spread = round(y10 - y2, 3)
        # Tính xu hướng spread 1 tuần
        if hist_10y is not None and hist_2y is not None and len(hist_10y)>=6 and len(hist_2y)>=6:
            spread_now = hist_10y.iloc[-1] - hist_2y.iloc[-1]
            spread_ago = hist_10y.iloc[-6] - hist_2y.iloc[-6]
            spread_chg = round(spread_now - spread_ago, 3)  # đổi tính bằng điểm %
            trend_str = f"{spread_chg:+.2f}pp" + (" ↑" if spread_chg > 0 else " ↓" if spread_chg < 0 else " →")
        else:
            trend_str = "N/A"
            spread_chg = None
        value_str = f"{spread:+.2f}% ({y2:.2f}% vs {y10:.2f}%)"
        status, label = evaluate("spread_2s10s", spread)
    else:
        spread = None
        spread_chg = None
        trend_str = "N/A"
        value_str = "N/A"
        status, label = "success", "Bình thường"

    return {
        "category": "",
        "indicator": "2s10s spread",
        "value": value_str,
        "trend": trend_str,
        "trend_raw": spread_chg,
        "threshold": "Đảo ngược âm",
        "status": status,
        "statusLabel": label,
        "source": "Yahoo Finance (2YY=F, ^TNX)",
        "link": "https://finance.yahoo.com/quote/%5ETNX/",
        "note": "Hiệu lợi suất 10Y – 2Y: âm = đường cong đảo ngược, tín hiệu suy thoái"
    }

# ===== RISK SCORE =====

def calc_risk_score(indicators):
    """
    Tính tổng điểm rủi ro (0-100) dựa trên framework:
    - Địa chính trị: 30%
    - Thị trường:    50%
    - Vĩ mô:         20%
    """
    # Bản đồ indicator -> giá trị thô
    vals = {ind["indicator"]: ind for ind in indicators}

    def raw(name):
        ind = vals.get(name, {})
        v = ind.get("value", "N/A")
        return v

    def raw_num(name):
        """Lấy giá trị số từ value string."""
        try:
            v = vals.get(name, {}).get("value", "")
            # Xóa ký tự không phải số
            import re
            nums = re.findall(r"[-+]?\d+\.?\d*", str(v))
            return float(nums[0]) if nums else None
        except:
            return None

    scores = {}
    details = {}

    # --- Dầu WTI (0-10) ---
    wti = raw_num("Dầu WTI")
    if wti is None:      wti_s = 0
    elif wti >= 110:     wti_s = 10
    elif wti >= 105:     wti_s = 9
    elif wti >= 100:     wti_s = 8
    elif wti >= 95:      wti_s = 7
    elif wti >= 90:      wti_s = 5
    elif wti >= 85:      wti_s = 3
    else:                wti_s = 0
    # Thưởng thêm 1 điểm nếu đang tăng tuần
    wti_trend = vals.get("Dầu WTI", {}).get("trend_raw") or 0
    if wti_trend > 3: wti_s = min(wti_s + 1, 10)
    scores["wti"] = wti_s

    # --- Xung đột Hormuz (0-10) ---
    hormuz_val = raw("Xung đột Hormuz")
    hormuz_s = 10 if "phông tỏa" in str(hormuz_val).lower() and "chưa" not in str(hormuz_val).lower() else 0
    scores["hormuz"] = hormuz_s

    # --- VIX (0-10) ---
    vix = raw_num("VIX")
    if vix is None:     vix_s = 0
    elif vix >= 45:     vix_s = 10
    elif vix >= 40:     vix_s = 9
    elif vix >= 35:     vix_s = 8
    elif vix >= 30:     vix_s = 7
    elif vix >= 25:     vix_s = 5
    elif vix >= 22:     vix_s = 3
    else:               vix_s = 0
    vix_trend = vals.get("VIX", {}).get("trend_raw") or 0
    if vix_trend > 10: vix_s = min(vix_s + 1, 10)
    scores["vix"] = vix_s

    # --- VIX futures curve (0-10) ---
    vix_curve_status = vals.get("VIX futures curve", {}).get("status", "success")
    if vix_curve_status == "danger":   vix_curve_s = 8
    elif vix_curve_status == "warning": vix_curve_s = 4
    else:                               vix_curve_s = 1
    scores["vix_curve"] = vix_curve_s

    # --- HYG/TLT ratio (0-10) ---
    hyg_trend = vals.get("HYG/TLT ratio", {}).get("trend_raw") or 0
    if hyg_trend <= -5:   hyg_s = 10
    elif hyg_trend <= -3: hyg_s = 6
    elif hyg_trend <= -1: hyg_s = 3
    else:                 hyg_s = 0
    scores["hyg_tlt"] = hyg_s

    # --- Put/Call ratio (0-10) ---
    pc = raw_num("Put/Call ratio")
    if pc is None:    pc_s = 3
    elif pc >= 1.3:   pc_s = 10
    elif pc >= 1.1:   pc_s = 8
    elif pc >= 0.95:  pc_s = 5
    elif pc >= 0.8:   pc_s = 3
    else:             pc_s = 1
    scores["put_call"] = pc_s

    # --- 10-year yield (0-10) ---
    y10 = raw_num("10-year yield")
    if y10 is None:   y10_s = 0
    elif y10 >= 5.0:  y10_s = 10
    elif y10 >= 4.7:  y10_s = 8
    elif y10 >= 4.5:  y10_s = 7
    elif y10 >= 4.3:  y10_s = 5
    elif y10 >= 4.0:  y10_s = 3
    else:             y10_s = 0
    scores["yield_10y"] = y10_s

    # --- 2s10s spread (0-10) ---
    spread_val = vals.get("2s10s spread", {}).get("value", "")
    import re
    sp_nums = re.findall(r"[+-]?\d+\.?\d*", str(spread_val))
    spread = float(sp_nums[0]) if sp_nums else None
    if spread is None:      sp_s = 0
    elif spread <= -0.5:    sp_s = 10
    elif spread <= -0.2:    sp_s = 7
    elif spread <= 0:       sp_s = 4
    elif spread <= 0.3:     sp_s = 1
    else:                   sp_s = 0
    scores["spread"] = sp_s

    # --- Tính điểm nhóm ---
    geo_score    = (scores["wti"] * 0.6 + scores["hormuz"] * 0.4)          # 30%
    market_score = (scores["vix"] * 0.35 + scores["vix_curve"] * 0.25
                   + scores["hyg_tlt"] * 0.20 + scores["put_call"] * 0.20) # 50%
    macro_score  = (scores["yield_10y"] * 0.5 + scores["spread"] * 0.5)    # 20%

    total = round(geo_score * 0.30 + market_score * 0.50 + macro_score * 0.20, 1)
    total = max(0, min(100, total * 10))  # scale 0-10 -> 0-100

    # Xác định mức
    if total <= 30:   level, color = "BÌNH THƯỜNG",        "success"
    elif total <= 50: level, color = "CẢNH GIÁC",          "warning"
    elif total <= 70: level, color = "CẢNH BÁO CAO",       "danger"
    else:             level, color = "RỦI RO HỆ THỐNG",   "critical"

    return {
        "score": total,
        "level": level,
        "color": color,
        "breakdown": {
            "geo":    round(geo_score * 10, 1),
            "market": round(market_score * 10, 1),
            "macro":  round(macro_score * 10, 1),
        },
        "indicator_scores": scores,
    }


def update_risk_history(risk):
    """Lưu điểm rủi ro vào risk_history.json (giữ 30 ngày)."""
    hist = []
    if os.path.exists(RISK_HISTORY):
        with open(RISK_HISTORY, encoding="utf-8") as f:
            hist = json.load(f)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    today = now.strftime("%Y-%m-%d")
    entry = {
        "date": today,
        "time": now.strftime("%H:%M"),
        "score": risk["score"],
        "level": risk["level"],
    }

    # Cập nhật entry hôm nay nếu đã có
    if hist and hist[-1]["date"] == today:
        hist[-1] = entry
    else:
        hist.append(entry)

    hist = hist[-30:]  # giữ 30 ngày gần nhất
    with open(RISK_HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    return hist


# ===== MAIN =====

def main():
    print("Đang fetch dữ liệu...")

    vix_row, vix_curve_row = fetch_vix()

    indicators = [
        fetch_wti(),
        fetch_hormuz(),
        vix_row,
        vix_curve_row,
        fetch_hyg_tlt(),
        fetch_put_call(),
        fetch_yield_10y(),
        fetch_spread_2s10s(),
    ]

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    result = {
        "last_updated": now.strftime("%H:%M %A, %d/%m/%Y (GMT+7)"),
        "indicators": indicators
    }

    # Tính risk score và lưu lịch sử
    risk = calc_risk_score(indicators)
    update_risk_history(risk)
    result["risk"] = risk

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved → {OUTPUT}")
    print(f"last_updated: {result['last_updated']}")
    print(f"Risk score: {risk['score']}/100 ({risk['level']})")
    for ind in indicators:
        print(f"  [{ind['status']:7}] {ind['indicator']:<22} = {ind['value']:<35} trend: {ind['trend']}")

if __name__ == "__main__":
    main()
