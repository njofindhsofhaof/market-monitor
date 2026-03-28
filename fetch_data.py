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
# Công thức theo framework của người dùng
import re as _re

def _get_num(s):
    """Lấy số đầu tiên từ string."""
    nums = _re.findall(r"[-+]?\d+\.?\d*", str(s))
    return float(nums[0]) if nums else None

def _oil_score(price, trend_pct):
    if price is None: return 0
    if price < 70:    s = 0
    elif price < 80:  s = 2
    elif price < 90:  s = 4
    elif price < 95:  s = 6
    elif price < 105: s = 8
    else:             s = 10
    if (trend_pct or 0) > 5:   s += 1
    elif (trend_pct or 0) > 2: s += 0.5
    return min(10, max(0, s))

def _hormuz_score(value_str):
    v = str(value_str).lower()
    if "phông tỏa" in v and "chưa" not in v:
        if "toàn bộ" in v or "hoàn toàn" in v: return 10
        if "một phần" in v or "cục bộ" in v:  return 7
        return 7
    if "căng thẳng" in v or "tension" in v: return 4
    return 0  # chưa phông tỏa

def _vix_score(vix, trend_pct):
    if vix is None: return 0
    if vix < 15:    s = 0
    elif vix < 20:  s = 2
    elif vix < 25:  s = 4
    elif vix < 30:  s = 6
    elif vix < 35:  s = 8
    else:           s = 10
    if (trend_pct or 0) > 10:  s += 1
    elif (trend_pct or 0) > 5: s += 0.5
    return min(10, max(0, s))

def _vix_curve_score(value_str, trend_pct):
    v = str(value_str).lower()
    if "deep backwardation" in v or "backwardation mạnh" in v: s = 10
    elif "backwardation" in v:                                    s = 8
    elif "phẳng" in v or "flat" in v:                           s = 6
    elif "contango nhẹ" in v or "light contango" in v:          s = 4
    elif "contango" in v:                                         s = 2
    else:                                                         s = 4
    # Đang tiến về backwardation
    if (trend_pct or 0) > 5 and s == 4: s += 1
    return min(10, max(0, s))

def _hyg_tlt_score(weekly_chg):
    if weekly_chg is None or weekly_chg >= 0: return 0
    decline = abs(weekly_chg)
    if decline < 2:  return 0
    if decline < 5:  return 2
    if decline < 10: return 5
    if decline < 15: return 8
    return 10

def _put_call_score(ratio):
    if ratio is None:  return 0
    if ratio < 0.7:    return 0
    if ratio < 0.9:    return 2
    if ratio < 1.1:    return 4
    if ratio < 1.3:    return 7
    return 10

def _yield_score(y10, trend_pct):
    if y10 is None: return 0
    if y10 < 3.5:   s = 0
    elif y10 < 4.0: s = 2
    elif y10 < 4.3: s = 4
    elif y10 < 4.5: s = 6
    elif y10 < 5.0: s = 8
    else:           s = 10
    if (trend_pct or 0) > 5: s += 1
    return min(10, max(0, s))

def _spread_score(spread, is_expanding):
    if spread is None: return 0
    if spread > 0.5:   return 0 if is_expanding else 1
    if spread > 0:     return 3
    if spread > -0.5:  return 6
    if spread > -1.0:  return 8
    return 10


def calc_risk_score(indicators):
    """
    Tính tổng điểm rủi ro (0-100) theo framework của người dùng.
    - Địa chính trị (geo):    30%  = trung bình(oil, hormuz)
    - Thị trường (market): 50%  = trung bình(vix, vix_curve, hyg_tlt, put_call)
    - Vĩ mô (macro):       20%  = trung bình(yield_10y, spread_2s10s)
    Tổng = (geo*0.3 + market*0.5 + macro*0.2) * 10
    """
    vals = {ind["indicator"]: ind for ind in indicators}

    def v(name):   return vals.get(name, {})
    def num(name): return _get_num(v(name).get("value", ""))
    def tr(name):  return v(name).get("trend_raw") or 0

    # --- Chấm điểm từng chỉ báo ---
    oil_s     = _oil_score(num("Dầu WTI"), tr("Dầu WTI"))
    hormuz_s  = _hormuz_score(v("Xung đột Hormuz").get("value", ""))
    vix_s     = _vix_score(num("VIX"), tr("VIX"))
    curve_s   = _vix_curve_score(v("VIX futures curve").get("value", ""), tr("VIX futures curve"))
    hyg_s     = _hyg_tlt_score(tr("HYG/TLT ratio"))
    pc_s      = _put_call_score(num("Put/Call ratio"))
    y10_s     = _yield_score(num("10-year yield"), tr("10-year yield"))

    # 2s10s spread: lấy số đầu tiên (spread bật), kiểm tra xu hướng
    spread_raw = v("2s10s spread").get("trend_raw") or 0
    spread_val_str = v("2s10s spread").get("value", "")
    spread_num = _get_num(spread_val_str)  # số đầu tiên = giá trị spread
    is_expanding = (spread_raw or 0) > 0   # spread đang mở rộng
    sp_s = _spread_score(spread_num, is_expanding)

    scores = {
        "oil": oil_s, "hormuz": hormuz_s,
        "vix": vix_s, "vix_curve": curve_s,
        "hyg_tlt": hyg_s, "put_call": pc_s,
        "yield_10y": y10_s, "spread": sp_s,
    }

    # --- Điểm nhóm (thang 0-10) ---
    geo_score    = (oil_s + hormuz_s) / 2
    market_score = (vix_s + curve_s + hyg_s + pc_s) / 4
    macro_score  = (y10_s + sp_s) / 2

    # --- Tổng điểm có trọng số -> thang 0-100 ---
    weighted = geo_score * 0.3 + market_score * 0.5 + macro_score * 0.2
    total = int(round(weighted * 10))
    total = max(0, min(100, total))

    # --- Xác định mức ---
    if total <= 30:   level, color = "BÌNH THƯỜNG",   "success"
    elif total <= 50: level, color = "CẢNH GIÁC",      "warning"
    elif total <= 70: level, color = "CẢNH BÁO CAO",   "danger"
    else:             level, color = "RỦI RO HỆ THỐNG", "critical"

    return {
        "score": total,
        "level": level,
        "color": color,
        "breakdown": {
            "geo":    round(geo_score * 10, 1),
            "market": round(market_score * 10, 1),
            "macro":  round(macro_score * 10, 1),
        },
        "indicator_scores": {k: round(s, 2) for k, s in scores.items()},
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
