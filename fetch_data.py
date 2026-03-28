"""
Script độc lập: fetch dữ liệu thị trường và ghi ra data.json
Chạy bởi GitHub Actions mỗi giờ.
"""
import json, datetime, os
import yfinance as yf

OUTPUT = os.path.join(os.path.dirname(__file__), "data.json")

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

def fetch_put_call():
    try:
        spy = yf.Ticker("SPY")
        exp = spy.options[0]
        chain = spy.option_chain(exp)
        c = chain.calls["volume"].sum()
        p = chain.puts["volume"].sum()
        ratio = round(float(p/c), 3) if c > 0 else None
        status, label = evaluate("put_call", ratio)
        return {
            "category": "",
            "indicator": "Put/Call ratio",
            "value": f"{ratio:.3f}" if ratio else "N/A",
            "trend": "—",   # intraday, không có 1w history
            "trend_raw": None,
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

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved → {OUTPUT}")
    print(f"last_updated: {result['last_updated']}")
    for ind in indicators:
        print(f"  [{ind['status']:7}] {ind['indicator']:<22} = {ind['value']:<35} trend: {ind['trend']}")

if __name__ == "__main__":
    main()
