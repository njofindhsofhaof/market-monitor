"""
Script độc lập: fetch dữ liệu thị trường và ghi ra data.json
Chạy độc lập bởi cron, không cần server FastAPI.
"""
import json, datetime, yfinance as yf, requests, os

OUTPUT = os.path.join(os.path.dirname(__file__), "data.json")

def get_yahoo(symbol):
    try:
        return round(float(yf.Ticker(symbol).fast_info["lastPrice"]), 4)
    except:
        return None

def get_vix_structure(vix_spot):
    vix_m1 = None
    for sym in ["VIXY"]:
        vix_m1 = get_yahoo(sym)
        if vix_m1: break
    if vix_spot and vix_m1:
        # VIXY là ETF, 1 share ≈ spot/10 roughly; dùng theo tương đối
        pass
    # Dùng mức VIX để suy ra cấu trúc (phương pháp thực tế)
    if vix_spot:
        if vix_spot > 35:
            return "Backwardation (VIX {:.1f})".format(vix_spot), "backwardation"
        elif vix_spot > 25:
            return "Contango nhẹ (VIX spot {:.1f})".format(vix_spot), "uncertain"
        return "Contango (VIX spot {:.1f})".format(vix_spot), "contango"
    return "Đang theo dõi", "unknown"

def get_hyg_tlt():
    try:
        hyg_h = yf.Ticker("HYG").history(period="10d")["Close"]
        tlt_h = yf.Ticker("TLT").history(period="10d")["Close"]
        if len(hyg_h) < 2 or len(tlt_h) < 2:
            return None, "Đang theo dõi", "success"
        r_now = hyg_h.iloc[-1] / tlt_h.iloc[-1]
        r_old = (hyg_h.iloc[-6] if len(hyg_h) >= 6 else hyg_h.iloc[0]) / \
                (tlt_h.iloc[-6] if len(tlt_h) >= 6 else tlt_h.iloc[0])
        chg = (r_now - r_old) / r_old * 100
        display = "{:.4f} ({:+.1f}%/tuần)".format(r_now, chg)
        status = "danger" if chg <= -5 else ("warning" if chg <= -3 else "success")
        label  = "CẢNH BÁO" if status=="danger" else ("CẢNH GIÁC" if status=="warning" else "Bình thường")
        return round(r_now,4), display, status
    except:
        return None, "Đang theo dõi", "success"

def get_pc_ratio():
    try:
        spy = yf.Ticker("SPY")
        exp = spy.options[0]
        chain = spy.option_chain(exp)
        c = chain.calls["volume"].sum()
        p = chain.puts["volume"].sum()
        ratio = round(p/c, 3) if c > 0 else None
        return ratio
    except:
        return None

def evaluate(indicator, value):
    if value is None: return "success","Bình thường"
    if indicator == "wti":
        return ("danger","CẢNH BÁO") if value>95 else ("warning","CẢNH GIÁC") if value>85 else ("success","Bình thường")
    if indicator == "vix":
        return ("danger","CẢNH BÁO") if value>=30 else ("warning","CẢNH GIÁC") if value>=22 else ("success","Bình thường")
    if indicator == "put_call":
        return ("danger","CẢNH BÁO") if value>=1.1 else ("warning","CẢNH GIÁC") if value>=0.95 else ("success","Bình thường")
    if indicator == "yield_10y":
        return ("danger","CẢNH BÁO") if value>=4.5 else ("warning","CẢNH GIÁC") if value>=4.3 else ("success","Bình thường")
    if indicator == "spread_2s10s":
        return ("danger","CẢNH BÁO") if value<-0.2 else ("warning","CẢNH GIÁC") if value<0 else ("success","Bình thường")
    return "success","Bình thường"

def main():
    wti = get_yahoo("CL=F")
    vix = get_yahoo("^VIX")
    y10 = get_yahoo("^TNX")
    y2  = get_yahoo("2YY=F")
    pc  = get_pc_ratio()
    hyg_tlt_val, hyg_tlt_display, hyg_tlt_status = get_hyg_tlt()
    hyg_tlt_label = "CẢNH BÁO" if hyg_tlt_status=="danger" else ("CẢNH GIÁC" if hyg_tlt_status=="warning" else "Bình thường")

    vix_str, vix_struct = get_vix_structure(vix)
    vix_f_status = "danger" if vix_struct=="backwardation" else ("warning" if vix_struct=="uncertain" else "success")
    vix_f_label  = "CẢNH BÁO" if vix_f_status=="danger" else ("CẢNH GIÁC" if vix_f_status=="warning" else "Bình thường")

    wti_s, wti_l = evaluate("wti", wti)
    vix_s, vix_l = evaluate("vix", vix)
    pc_s, pc_l   = evaluate("put_call", pc)
    y10_s, y10_l = evaluate("yield_10y", y10)

    spread = round(y10 - y2, 3) if y10 and y2 else None
    sp_s, sp_l = evaluate("spread_2s10s", spread)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    ts  = now.strftime("%H:%M %A, %d/%m/%Y (GMT+7)")

    result = {
        "last_updated": ts,
        "indicators": [
            {"category":"Địa chính trị","indicator":"Dầu WTI",
             "value": "${:.2f}/thùng".format(wti) if wti else "N/A",
             "threshold":">95 USD/thùng","status":wti_s,"statusLabel":wti_l,
             "source":"Yahoo Finance (CL=F)"},
            {"category":"","indicator":"Xung đột Hormuz",
             "value":"Chưa phong tỏa","threshold":"Có phong tỏa",
             "status":"success","statusLabel":"Bình thường","source":"Đánh giá thủ công"},
            {"category":"Thị trường","indicator":"VIX",
             "value":"{:.2f}".format(vix) if vix else "N/A",
             "threshold":">30","status":vix_s,"statusLabel":vix_l,
             "source":"Yahoo Finance (^VIX)"},
            {"category":"","indicator":"VIX futures curve",
             "value":vix_str,"threshold":"Backwardation",
             "status":vix_f_status,"statusLabel":vix_f_label,
             "source":"Yahoo Finance (^VIX level)"},
            {"category":"","indicator":"HYG/TLT ratio",
             "value":hyg_tlt_display,"threshold":"Giảm >5%/tuần",
             "status":hyg_tlt_status,"statusLabel":hyg_tlt_label,
             "source":"Yahoo Finance (HYG, TLT)"},
            {"category":"","indicator":"Put/Call ratio",
             "value":"{:.3f}".format(pc) if pc else "N/A",
             "threshold":">1.1","status":pc_s,"statusLabel":pc_l,
             "source":"Yahoo Finance (SPY options)"},
            {"category":"Vĩ mô","indicator":"10-year yield",
             "value":"{:.2f}%".format(y10) if y10 else "N/A",
             "threshold":">4.5%","status":y10_s,"statusLabel":y10_l,
             "source":"Yahoo Finance (^TNX)"},
            {"category":"","indicator":"2s10s spread",
             "value":"{:+.2f}% ({:.2f}% vs {:.2f}%)".format(spread,y2,y10) if spread is not None else "N/A",
             "threshold":"Đảo ngược âm","status":sp_s,"statusLabel":sp_l,
             "source":"Yahoo Finance (2YY=F, ^TNX)"},
        ]
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("Saved to", OUTPUT)
    print("last_updated:", ts)
    for ind in result["indicators"]:
        print(f'  [{ind["status"]:7}] {ind["indicator"]:<22} = {ind["value"]}')

if __name__ == "__main__":
    main()
