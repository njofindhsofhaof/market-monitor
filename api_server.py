"""
Backend API server — Bảng Tổng Hợp Theo Dõi Hàng Ngày
Nguồn: Yahoo Finance (không cần API key) + FRED public CSV
Cập nhật: dữ liệu được cache trong bộ nhớ, refresh mỗi 1 giờ
"""

import time
import threading
import datetime
import requests
import yfinance as yf
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Market Monitor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ===== CACHE =====
_cache = {
    "data": None,
    "last_updated": None,
    "error": None,
}
CACHE_TTL_SECONDS = 3600  # 1 giờ


# ===== HÀM LẤY DỮ LIỆU =====

def get_yahoo(symbol: str) -> float | None:
    try:
        t = yf.Ticker(symbol)
        return round(float(t.fast_info["lastPrice"]), 4)
    except Exception:
        return None


def get_fred_series(series_id: str) -> float | None:
    """Lấy giá trị mới nhất từ FRED public CSV (không cần API key)."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        lines = [l for l in resp.text.strip().split("\n") if l and not l.startswith("DATE")]
        for line in reversed(lines):
            parts = line.split(",")
            if len(parts) == 2 and parts[1].strip() not in (".", ""):
                return round(float(parts[1]), 4)
    except Exception:
        pass
    return None


def get_spy_put_call_ratio() -> float | None:
    """Tính Put/Call ratio từ SPY options chain (nearest expiry)."""
    try:
        spy = yf.Ticker("SPY")
        exp = spy.options[0]
        chain = spy.option_chain(exp)
        calls_vol = chain.calls["volume"].sum()
        puts_vol = chain.puts["volume"].sum()
        if calls_vol > 0:
            return round(float(puts_vol / calls_vol), 3)
    except Exception:
        pass
    return None


def get_vix_futures_structure() -> tuple[str, str]:
    """
    Xác định cấu trúc VIX futures: Contango hay Backwardation.
    So sánh VIX spot vs VIX M1 (^VX=F) và M2 futures.
    Trả về (display_string, structure_type)
    """
    try:
        vix_spot = get_yahoo("^VIX")
        # Thử các ticker VIX futures
        vix_m1 = None
        for sym in ["^VX=F", "VX=F", "VIXY"]:
            vix_m1 = get_yahoo(sym)
            if vix_m1:
                break

        if vix_spot and vix_m1:
            diff = vix_m1 - vix_spot
            if diff > 0.5:
                return f"Contango nhẹ (M1 {vix_m1:.1f} > spot {vix_spot:.1f})", "contango"
            elif diff > 1.5:
                return f"Contango mạnh (M1 {vix_m1:.1f} >> spot {vix_spot:.1f})", "contango"
            elif diff < -0.5:
                return f"Backwardation (M1 {vix_m1:.1f} < spot {vix_spot:.1f})", "backwardation"
            else:
                return f"Phẳng (M1 {vix_m1:.1f} ≈ spot {vix_spot:.1f})", "flat"
    except Exception:
        pass
    # Fallback: suy ra cấu trúc từ mức VIX spot
    vix_spot = get_yahoo("^VIX")
    if vix_spot:
        if vix_spot > 30:
            # VIX cao thường đi kèm backwardation
            return f"Contango nhẹ (VIX spot: {vix_spot:.1f}, cần theo dõi)", "uncertain"
        return f"Contango nhẹ (VIX spot: {vix_spot:.1f})", "contango"
    return "Không có dữ liệu", "unknown"


def get_hyg_tlt_ratio() -> tuple[float | None, str]:
    """Tính HYG/TLT ratio và so sánh với 5 ngày trước để xác định xu hướng."""
    try:
        import pandas as pd
        hyg = yf.Ticker("HYG")
        tlt = yf.Ticker("TLT")

        hyg_hist = hyg.history(period="10d")["Close"]
        tlt_hist = tlt.history(period="10d")["Close"]

        if len(hyg_hist) < 2 or len(tlt_hist) < 2:
            return None, "Không đủ dữ liệu"

        ratio_now = hyg_hist.iloc[-1] / tlt_hist.iloc[-1]
        ratio_5d_ago = hyg_hist.iloc[-6] / tlt_hist.iloc[-6] if len(hyg_hist) >= 6 else hyg_hist.iloc[0] / tlt_hist.iloc[0]
        change_pct = (ratio_now - ratio_5d_ago) / ratio_5d_ago * 100

        ratio_str = f"{ratio_now:.4f} ({change_pct:+.1f}%/tuần)"
        return round(ratio_now, 4), ratio_str
    except Exception:
        return None, "Đang theo dõi"


# ===== ĐÁNH GIÁ TRẠNG THÁI =====

def evaluate_status(indicator: str, value) -> tuple[str, str]:
    """
    Trả về (status, statusLabel) dựa trên ngưỡng cảnh báo.
    status: 'danger' | 'warning' | 'success'
    """
    if value is None:
        return "success", "Bình thường"

    if indicator == "wti":
        if value > 105:
            return "danger", "CẢNH BÁO"
        elif value > 95:
            return "danger", "CẢNH BÁO"
        elif value > 85:
            return "warning", "CẢNH GIÁC"
        return "success", "Bình thường"

    elif indicator == "vix":
        if value >= 30:
            return "danger", "CẢNH BÁO"
        elif value >= 22:
            return "warning", "CẢNH GIÁC"
        return "success", "Bình thường"

    elif indicator == "hyg_tlt_change":
        if value <= -5:
            return "danger", "CẢNH BÁO"
        elif value <= -3:
            return "warning", "CẢNH GIÁC"
        return "success", "Bình thường"

    elif indicator == "put_call":
        if value >= 1.1:
            return "danger", "CẢNH BÁO"
        elif value >= 0.95:
            return "warning", "CẢNH GIÁC"
        return "success", "Bình thường"

    elif indicator == "yield_10y":
        if value >= 4.5:
            return "danger", "CẢNH BÁO"
        elif value >= 4.3:
            return "warning", "CẢNH GIÁC"
        return "success", "Bình thường"

    elif indicator == "spread_2s10s":
        # Âm = đảo ngược (inverted) = cảnh báo suy thoái
        if value < -0.2:
            return "danger", "CẢNH BÁO"
        elif value < 0:
            return "warning", "CẢNH GIÁC"
        return "success", "Bình thường"

    return "success", "Bình thường"


# ===== FETCH TẤT CẢ DỮ LIỆU =====

def fetch_all_data() -> dict:
    print(f"[{datetime.datetime.now()}] Đang cập nhật dữ liệu...")

    # --- Giá dầu WTI ---
    wti = get_yahoo("CL=F")
    wti_status, wti_label = evaluate_status("wti", wti)
    wti_display = f"${wti:.2f}/thùng" if wti else "N/A"

    # --- VIX ---
    vix = get_yahoo("^VIX")
    vix_status, vix_label = evaluate_status("vix", vix)
    vix_display = f"{vix:.2f}" if vix else "N/A"

    # --- VIX Futures Structure ---
    vix_futures_str, vix_structure_type = get_vix_futures_structure()
    if vix_structure_type == "backwardation":
        vix_futures_status = "danger"
        vix_futures_label = "CẢNH BÁO"
    elif vix_structure_type in ("flat", "uncertain"):
        vix_futures_status = "warning"
        vix_futures_label = "CẢNH GIÁC"
    else:
        vix_futures_status = "success"
        vix_futures_label = "Bình thường"

    # --- HYG/TLT ratio ---
    hyg_tlt_ratio, hyg_tlt_display = get_hyg_tlt_ratio()
    # Tính % thay đổi để đánh giá
    try:
        import yfinance as yf2
        hyg_hist = yf2.Ticker("HYG").history(period="10d")["Close"]
        tlt_hist = yf2.Ticker("TLT").history(period="10d")["Close"]
        ratio_now = hyg_hist.iloc[-1] / tlt_hist.iloc[-1]
        ratio_5d_ago = hyg_hist.iloc[-6] / tlt_hist.iloc[-6] if len(hyg_hist) >= 6 else hyg_hist.iloc[0] / tlt_hist.iloc[0]
        change_pct = (ratio_now - ratio_5d_ago) / ratio_5d_ago * 100
        hyg_tlt_status, hyg_tlt_label = evaluate_status("hyg_tlt_change", change_pct)
    except Exception:
        hyg_tlt_status, hyg_tlt_label = "success", "Bình thường"

    # --- Put/Call ratio ---
    pc_ratio = get_spy_put_call_ratio()
    pc_status, pc_label = evaluate_status("put_call", pc_ratio)
    pc_display = f"{pc_ratio:.3f}" if pc_ratio else "N/A"

    # --- 10-year yield ---
    yield_10y = get_yahoo("^TNX")
    yield_10y_status, yield_10y_label = evaluate_status("yield_10y", yield_10y)
    yield_display = f"{yield_10y:.2f}%" if yield_10y else "N/A"

    # --- 2s10s spread (Yahoo Finance: 2YY=F và ^TNX) ---
    y10 = yield_10y  # đã lấy ở trên (^TNX)
    y2  = get_yahoo("2YY=F")  # 2-Year Treasury Yield futures
    if y10 and y2:
        spread = round(y10 - y2, 3)
        spread_display = f"{spread:+.2f}% ({y2:.2f}% vs {y10:.2f}%)"
    else:
        # Fallback: thử FRED nếu Yahoo lỗi
        y2_fred = get_fred_series("DGS2")
        y10_fred = get_fred_series("DGS10")
        if y2_fred and y10_fred:
            spread = round(y10_fred - y2_fred, 3)
            spread_display = f"{spread:+.2f}% ({y2_fred:.2f}% vs {y10_fred:.2f}%)"
        else:
            spread = None
            spread_display = "N/A"
    spread_status, spread_label = evaluate_status("spread_2s10s", spread)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    timestamp = now.strftime("%H:%M %A, %d/%m/%Y (GMT+7)")

    result = {
        "last_updated": timestamp,
        "indicators": [
            {
                "category": "Địa chính trị",
                "indicator": "Dầu WTI",
                "value": wti_display,
                "raw_value": wti,
                "threshold": ">95 USD/thùng",
                "status": wti_status,
                "statusLabel": wti_label,
                "source": "Yahoo Finance (CL=F)",
                "note": "Giá dầu thô WTI giao ngay (futures front-month)"
            },
            {
                "category": "",
                "indicator": "Xung đột Hormuz",
                "value": "Chưa phong tỏa",
                "raw_value": None,
                "threshold": "Có phong tỏa",
                "status": "success",
                "statusLabel": "Bình thường",
                "source": "Đánh giá thủ công",
                "note": "Eo biển Hormuz — không có API, cần cập nhật thủ công khi có sự kiện"
            },
            {
                "category": "Thị trường",
                "indicator": "VIX",
                "value": vix_display,
                "raw_value": vix,
                "threshold": ">30",
                "status": vix_status,
                "statusLabel": vix_label,
                "source": "Yahoo Finance (^VIX)",
                "note": "CBOE Volatility Index — chỉ số sợ hãi thị trường"
            },
            {
                "category": "",
                "indicator": "VIX futures curve",
                "value": vix_futures_str,
                "raw_value": None,
                "threshold": "Backwardation",
                "status": vix_futures_status,
                "statusLabel": vix_futures_label,
                "source": "Yahoo Finance (VXc1)",
                "note": "Cấu trúc kỳ hạn VIX futures: Contango = bình thường, Backwardation = căng thẳng"
            },
            {
                "category": "",
                "indicator": "HYG/TLT ratio",
                "value": hyg_tlt_display,
                "raw_value": hyg_tlt_ratio,
                "threshold": "Giảm >5%/tuần",
                "status": hyg_tlt_status,
                "statusLabel": hyg_tlt_label,
                "source": "Yahoo Finance (HYG, TLT)",
                "note": "Tỷ lệ trái phiếu rủi ro cao / trái phiếu dài hạn — đo khẩu vị rủi ro thị trường"
            },
            {
                "category": "",
                "indicator": "Put/Call ratio",
                "value": pc_display,
                "raw_value": pc_ratio,
                "threshold": ">1.1",
                "status": pc_status,
                "statusLabel": pc_label,
                "source": "Yahoo Finance (SPY options)",
                "note": "Tỷ lệ Put/Call từ SPY options nearest expiry — đo mức độ phòng thủ của nhà đầu tư"
            },
            {
                "category": "Vĩ mô",
                "indicator": "10-year yield",
                "value": yield_display,
                "raw_value": yield_10y,
                "threshold": ">4.5%",
                "status": yield_10y_status,
                "statusLabel": yield_10y_label,
                "source": "Yahoo Finance (^TNX)",
                "note": "Lợi suất trái phiếu Mỹ 10 năm — ảnh hưởng đến định giá cổ phiếu"
            },
            {
                "category": "",
                "indicator": "2s10s spread",
                "value": spread_display,
                "raw_value": spread,
                "threshold": "Đảo ngược âm",
                "status": spread_status,
                "statusLabel": spread_label,
                "source": "Yahoo Finance (2YY=F, ^TNX)",
                "note": "Hiệu lợi suất 10Y – 2Y: âm = đường cong đảo ngược, tín hiệu suy thoái tiềm năng"
            },
        ]
    }

    print(f"[{datetime.datetime.now()}] Cập nhật thành công.")
    return result


# ===== CACHE REFRESH LOGIC =====

def refresh_cache():
    global _cache
    try:
        data = fetch_all_data()
        _cache["data"] = data
        _cache["last_updated"] = time.time()
        _cache["error"] = None
    except Exception as e:
        _cache["error"] = str(e)
        print(f"Lỗi cập nhật cache: {e}")


def background_refresh():
    """Chạy trong background thread, refresh mỗi 1 giờ."""
    while True:
        refresh_cache()
        time.sleep(CACHE_TTL_SECONDS)


# ===== API ROUTES =====

@app.get("/api/data")
def get_data():
    """Trả về dữ liệu hiện tại từ cache. Nếu cache cũ hơn 1h, trigger refresh."""
    now = time.time()
    if _cache["data"] is None:
        # Lần đầu: fetch đồng bộ
        refresh_cache()
    elif _cache["last_updated"] and (now - _cache["last_updated"]) > CACHE_TTL_SECONDS:
        # Cache hết hạn: refresh ngầm (trả dữ liệu cũ trước)
        threading.Thread(target=refresh_cache, daemon=True).start()

    return {
        "success": True,
        "cache_age_minutes": round((now - (_cache["last_updated"] or now)) / 60, 1),
        **(_cache["data"] or {})
    }


@app.get("/api/refresh")
def force_refresh():
    """Force refresh ngay lập tức (dùng cho nút Refresh thủ công)."""
    refresh_cache()
    return {"success": True, "message": "Đã cập nhật xong"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "last_updated": _cache.get("last_updated"),
        "error": _cache.get("error")
    }


# ===== SERVE STATIC FILES =====
app.mount("/", StaticFiles(directory=".", html=True), name="static")


# ===== STARTUP =====
@app.on_event("startup")
async def startup_event():
    # Fetch lần đầu ngay khi server khởi động
    threading.Thread(target=refresh_cache, daemon=True).start()
    # Bắt đầu background refresh loop
    threading.Thread(target=background_refresh, daemon=True).start()
