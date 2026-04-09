"""
Script độc lập: fetch dữ liệu thị trường và ghi ra data.json
Chạy bởi GitHub Actions mỗi giờ.
"""
import json, datetime, os, re as _re
import requests
import yfinance as yf

OUTPUT        = os.path.join(os.path.dirname(__file__), "data.json")
PC_HISTORY    = os.path.join(os.path.dirname(__file__), "pc_history.json")
RISK_HISTORY  = os.path.join(os.path.dirname(__file__), "risk_history.json")
COT_HISTORY   = os.path.join(os.path.dirname(__file__), "cot_history.json")
AAII_HISTORY  = os.path.join(os.path.dirname(__file__), "aaii_history.json")
NAAIM_HISTORY = os.path.join(os.path.dirname(__file__), "naaim_history.json")
ETF_HISTORY   = os.path.join(os.path.dirname(__file__), "etf_history.json")
HORMUZ_CACHE  = os.path.join(os.path.dirname(__file__), "hormuz_cache.json")

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
    if indicator == "cot_net":
        # shortRatio = |net| / historicalMaxShort → đánh giá theo ngưỡng tương đối
        return (("danger","CẢNH BÁO") if value >= 0.7 else
                ("warning","CẢNH GIÁC") if value >= 0.4 else
                ("success","Bình thường"))
    if indicator == "etf_flow":
        # Flow 7 ngày (tỷ USD)
        return (("danger","CẢNH BÁO") if value < -5 else
                ("warning","CẢNH GIÁC") if value < -2 else
                ("success","Bình thường"))
    if indicator == "sentiment_diff":
        # retailBull% − instBull% (AAII vs NAAIM)
        return (("danger","CẢNH BÁO") if value >= 25 else
                ("warning","CẢNH GIÁC") if value >= 15 else
                ("success","Bình thường"))
    if indicator == "dxy":
        return (("danger","CẢNH BÁO") if value >= 107 else
                ("warning","CẢNH GIÁC") if value >= 105 else
                ("success","Bình thường"))
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
    """
    Xung đột Hormuz — scrape RSS mỗi giờ, chỉ xét tin trong vòng 24h gần nhất.
    Parse <pubDate> của từng item để đảm bảo dữ liệu mới.

    Mức độ:
      full_blockade    → score 10
      partial_blockade → score 7   (tàu bị tấn công/bắt giữ)
      tension          → score 4   (căng thẳng, đối đầu)
      none             → score 0
    """
    import email.utils  # parse RFC 2822 pubDate chuẩn RSS

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    cutoff  = now_utc - datetime.timedelta(hours=24)

    RSS_FEEDS = [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ]

    KEYWORDS_FULL = [
        "hormuz blockade", "strait of hormuz closed", "hormuz closed",
        "full blockade hormuz", "complete blockade hormuz",
    ]
    KEYWORDS_PARTIAL = [
        "ship seized hormuz", "tanker seized", "vessel seized strait",
        "attack tanker hormuz", "hormuz attack", "mine hormuz",
        "tanker captured", "seized in the strait", "partial blockade hormuz",
        "drone attack tanker", "missile tanker", "warship seized",
    ]
    KEYWORDS_TENSION = [
        "strait of hormuz", "hormuz tension", "hormuz standoff",
        "iran naval hormuz", "iran blocks", "iran threatens strait",
        "persian gulf standoff", "gulf military escalation",
        "iran warship confrontation", "hormuz warning",
    ]
    # Keyword rộng hơn — chỉ dùng nếu cụm trên không match
    KEYWORDS_TENSION_BROAD = [
        "hormuz",
    ]

    fresh_items   = []   # (text, pub_dt) — chỉ tin trong 24h
    all_items     = []   # tất cả items (dùng đếm tổng)
    fetch_errors  = []
    feed_stats    = []

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MarketMonitor/1.0)",
        "Accept":     "application/rss+xml, application/xml, text/xml",
    }

    for feed_url in RSS_FEEDS:
        source_name = feed_url.split("/")[2].replace("feeds.", "").replace("www.", "")
        try:
            resp = requests.get(feed_url, timeout=15, headers=headers)
            resp.raise_for_status()
            xml = resp.text

            # Parse từng <item> block riêng biệt
            items_xml = _re.findall(r"<item[^>]*>(.*?)</item>", xml, _re.DOTALL)
            count_fresh = 0

            for item_xml in items_xml:
                # Lấy title + description
                title_m = _re.search(r"<title[^>]*>(.*?)</title>", item_xml, _re.DOTALL)
                desc_m  = _re.search(r"<description[^>]*>(.*?)</description>", item_xml, _re.DOTALL)
                pub_m   = _re.search(r"<pubDate[^>]*>(.*?)</pubDate>", item_xml, _re.DOTALL)

                text = ""
                if title_m: text += _re.sub(r"<[^>]+>|&[a-z]+;", " ", title_m.group(1)).strip()
                if desc_m:  text += " " + _re.sub(r"<[^>]+>|&[a-z]+;", " ", desc_m.group(1)).strip()
                text = text.lower().strip()

                all_items.append(text)

                # Parse pubDate → check trong 24h
                pub_dt = None
                if pub_m:
                    try:
                        pub_str = pub_m.group(1).strip()
                        # email.utils.parsedate_to_datetime hỗ trợ RFC 2822
                        pub_dt = email.utils.parsedate_to_datetime(pub_str)
                        # Chuẩn hóa về UTC nếu có timezone
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=datetime.timezone.utc)
                    except Exception:
                        pub_dt = None

                if pub_dt and pub_dt >= cutoff:
                    fresh_items.append((text, pub_dt))
                    count_fresh += 1
                elif pub_dt is None:
                    # Không parse được pubDate → giữ lại, đánh dấu uncertain
                    fresh_items.append((text, None))

            feed_stats.append(f"{source_name}: {count_fresh}/{len(items_xml)} tin mới")

        except Exception as e:
            fetch_errors.append(f"{source_name}: {e}")
            feed_stats.append(f"{source_name}: lỗi")

    # ── Classify bằng Claude API — hiểu ngữ cảnh, không phụ thuộc keyword ──────
    # Lấy tất cả headlines trong 24h (không chỉ Hormuz keywords)
    # Gửi cho Claude để đánh giá nguy cơ gián đoạn eo biển Hormuz

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    def classify_with_claude(headlines_text):
        """Dùng Claude để đánh giá nguy cơ Hormuz từ headlines. Trả về dict."""
        if not ANTHROPIC_API_KEY or not headlines_text.strip():
            return None
        try:
            prompt = f"""Bạn là chuyên gia phân tích địa chính trị Trung Đông.

Dưới đây là các tin tức trong 24 giờ qua từ Reuters, BBC, Al Jazeera:

{headlines_text}

Hãy đánh giá mức độ rủi ro gián đoạn eo biển Hormuz dựa trên các tin này.
Xem xét cả các tin gián tiếp như: xung đột Mỹ-Iran, tấn công tàu vùng Vịnh, căng thẳng quân sự,
lính đổ bộ, phong tỏa, tập trận chiến tranh, đe dọa tên lửa, v.v.

Trả lời ĐÚNG FORMAT sau, không thêm gì khác:
LEVEL: <none|tension|partial_blockade|full_blockade>
VALUE: <mô tả ngắn bằng tiếng Việt, tối đa 8 từ>
REASON: <lý do ngắn gọn, tối đa 15 từ tiếng Việt>

Định nghĩa mức:
- none: Không có nguy cơ nào đáng kể với Hormuz
- tension: Căng thẳng ngoại giao/quân sự có thể ảnh hưởng Hormuz
- partial_blockade: Tàu bị tấn công/bắt giữ, hoặc leo thang nghiêm trọng
- full_blockade: Eo biển bị phong tỏa thực sự"""

            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 120,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=20
            )
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"].strip()

            level, value, reason = "none", "Bình thường", ""
            for line in text.splitlines():
                if line.startswith("LEVEL:"):
                    level = line.split(":",1)[1].strip().lower()
                elif line.startswith("VALUE:"):
                    value = line.split(":",1)[1].strip()
                elif line.startswith("REASON:"):
                    reason = line.split(":",1)[1].strip()
            return {"level": level, "value": value, "reason": reason}
        except Exception as e:
            print(f"[Hormuz] Claude API error: {type(e).__name__}: {e}", flush=True)
            return None

    # Chuẩn bị headlines (tối đa 30 tin, ưu tiên tin đề cập Hormuz/Iran/Gulf)
    priority_kw = ["hormuz", "iran", "gulf", "strait", "persian", "tanker",
                   "warship", "naval", "missile", "attack", "blockade",
                   "us troops", "marines", "invasion", "escalat"]
    sorted_fresh = sorted(
        fresh_items,
        key=lambda x: (
            sum(1 for kw in priority_kw if kw in x[0]),
            x[1] or datetime.datetime(1970,1,1,tzinfo=datetime.timezone.utc)
        ),
        reverse=True
    )
    top_headlines = sorted_fresh[:30]
    headlines_text = "\n".join(
        f"- {t[:200]}" for t, _ in top_headlines if t.strip()
    )

    # Thử Claude API trước
    has_key = bool(ANTHROPIC_API_KEY)
    print(f"[Hormuz] ANTHROPIC_API_KEY present: {has_key}, headlines: {len(top_headlines)}", flush=True)
    claude_result = classify_with_claude(headlines_text)

    if claude_result:
        level_key  = claude_result["level"]
        value_str  = claude_result["value"]
        ai_reason  = claude_result["reason"]
        status_map = {
            "full_blockade":    ("danger",  "CẢNH BÁO"),
            "partial_blockade": ("danger",  "CẢNH BÁO"),
            "tension":          ("warning", "CẢNH GIÁC"),
            "none":             ("success", "Bình thường"),
        }
        status, label = status_map.get(level_key, ("success", "Bình thường"))
        classify_source = f"Claude AI ({len(top_headlines)} headlines)"
    else:
        # Fallback: keyword matching nếu không có API key hoặc API lỗi
        fresh_texts = " | ".join(t for t, _ in fresh_items)
        def any_match(keywords):
            return any(kw in fresh_texts for kw in keywords)

        KEYWORDS_FULL    = ["hormuz blockade","strait of hormuz closed","hormuz closed","full blockade hormuz"]
        KEYWORDS_PARTIAL = ["ship seized hormuz","tanker seized","vessel seized strait",
                            "attack tanker hormuz","hormuz attack","tanker captured","partial blockade hormuz",
                            "drone attack tanker","missile tanker","warship seized"]
        KEYWORDS_TENSION = ["strait of hormuz","hormuz tension","hormuz standoff",
                            "iran naval hormuz","iran blocks","iran threatens strait",
                            "persian gulf standoff","gulf military escalation","hormuz warning"]
        KEYWORDS_BROAD   = ["hormuz"]

        if any_match(KEYWORDS_FULL):
            level_key, value_str, status, label = "full_blockade", "Phong tỏa hoàn toàn", "danger", "CẢNH BÁO"
        elif any_match(KEYWORDS_PARTIAL):
            level_key, value_str, status, label = "partial_blockade", "Phong tỏa một phần / tàu bị tấn công", "danger", "CẢNH BÁO"
        elif any_match(KEYWORDS_TENSION):
            level_key, value_str, status, label = "tension", "Căng thẳng leo thang", "warning", "CẢNH GIÁC"
        elif any_match(KEYWORDS_BROAD):
            level_key, value_str, status, label = "tension", "Có đề cập — theo dõi thêm", "warning", "CẢNH GIÁC"
        else:
            level_key, value_str, status, label = "none", "Bình thường", "success", "Bình thường"
        ai_reason = ""
        classify_source = "keyword fallback"

    # Tìm headline nổi bật nhất (Hormuz/Iran/Gulf)
    hormuz_fresh = sorted(
        [(t, dt) for t, dt in fresh_items
         if any(kw in t for kw in ["hormuz","strait","iran","gulf","tanker","warship"])],
        key=lambda x: x[1] or datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc),
        reverse=True
    )

    top_headline = ""
    if hormuz_fresh:
        raw = hormuz_fresh[0][0][:120].capitalize()
        pub = hormuz_fresh[0][1]
        time_str = pub.strftime("%H:%M UTC") if pub else "?"
        top_headline = f'"{raw}..." ({time_str})'

    note_parts = [
        f"RSS scan {now_utc.strftime('%H:%M UTC')}: "
        f"{len(fresh_items)} tin <24h / {len(all_items)} tổng ({', '.join(feed_stats)})",
        f"Phân tích: {classify_source}",
    ]
    if ai_reason:
        note_parts.append(f"Lý do: {ai_reason}")
    if top_headline:
        note_parts.append(f"Headline: {top_headline}")
    if fetch_errors:
        note_parts.append(f"Lỗi feed: {'; '.join(fetch_errors)}")

    result = {
        "category": "",
        "indicator": "Xung đột Hormuz",
        "value": value_str,
        "trend": "—",
        "trend_raw": None,
        "threshold": "Có phong tỏa",
        "status": status,
        "statusLabel": label,
        "source": "Reuters · BBC · Al Jazeera (RSS tự động, 24h)",
        "link": "https://www.reuters.com/search/news?blob=Strait+of+Hormuz",
        "note": " | ".join(note_parts),
        "_meta": {
            "status_key":      level_key,
            "hormuz_count":    len(hormuz_fresh),
            "fresh_total":     len(fresh_items),
            "scanned_at":      now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "classify_source": classify_source,
        }
    }

    # ── Lưu cache (để debug / fallback nếu feed lỗi toàn bộ) ──────
    try:
        with open(HORMUZ_CACHE, "w", encoding="utf-8") as f:
            json.dump({
                "scanned_at": now_utc.isoformat(),
                "result": result
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return result


# ===== DÒNG TIỀN TỔ CHỨC =====

def _load_cot_history():
    if os.path.exists(COT_HISTORY):
        with open(COT_HISTORY, encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_cot_history(net_k, short_k):
    """Lưu net và short riêng để tính rolling max short."""
    hist = _load_cot_history()
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%Y-%m-%d")
    entry = {"date": today, "net": net_k, "short": short_k}
    if hist and hist[-1]["date"] == today:
        hist[-1] = entry
    else:
        hist.append(entry)
    hist = hist[-104:]  # giữ ~2 năm (104 tuần)
    with open(COT_HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    return hist

def _get_historical_max_short():
    """Rolling max short từ lịch sử COT (K contracts)."""
    hist = _load_cot_history()
    shorts = [abs(e["short"]) for e in hist if e.get("short") is not None and e["short"] < 0]
    if not shorts:
        return 350.0  # fallback: giá trị lịch sử điển hình S&P 500 E-mini
    return max(shorts)

def fetch_cot():
    """
    COT Report — Commercial net positioning trên S&P 500 E-mini futures.

    Nguồn 1 (ưu tiên): Nasdaq Data Link API (CFTC/ES_FO_L_ALL)
      - API key từ env var NASDAQ_API_KEY (set trong GitHub Actions Secret)
      - Dataset: Legacy Futures-Only, S&P 500 E-mini
      - Cột: Commercial Long, Commercial Short

    Nguồn 2 (fallback): CFTC static TXT file FinFutWk.txt
      - Traders in Financial Futures, Dealers long/short
      - Không cần API key, không bị block

    shortRatio = |commercial_net| / historicalMaxShort (rolling max 104 tuần)
    """
    import csv, io

    NASDAQ_KEY = os.environ.get("NASDAQ_API_KEY", "")

    # ── Nguồn 1: Nasdaq Data Link ──────────────────────────────────
    if NASDAQ_KEY:
        try:
            url = (f"https://data.nasdaq.com/api/v3/datasets/CFTC/ES_FO_L_ALL/data.json"
                   f"?rows=2&api_key={NASDAQ_KEY}")
            resp = requests.get(url, timeout=20,
                                headers={"User-Agent": "python-requests/2.31.0"})
            resp.raise_for_status()
            data = resp.json()

            rows   = data["dataset_data"]["data"]      # [[date, col1, col2, ...], ...]
            cols   = data["dataset_data"]["column_names"]  # ['Date', 'Open Interest', ...]

            # Tìm index cột Commercial Long / Short
            ci = {c.lower(): i for i, c in enumerate(cols)}
            comm_long_i  = next((ci[k] for k in ci if "commercial" in k and "long"  in k), None)
            comm_short_i = next((ci[k] for k in ci if "commercial" in k and "short" in k), None)

            if comm_long_i is None or comm_short_i is None:
                raise ValueError(f"Không tìm thấy cột Commercial. Cols: {cols}")

            row0        = rows[0]
            report_date = row0[0]
            comm_long   = int(row0[comm_long_i]  or 0)
            comm_short  = int(row0[comm_short_i] or 0)
            net         = comm_long - comm_short
            net_k       = round(net / 1000, 1)
            short_k     = round(comm_short / 1000, 1)

            # WoW từ row[1]
            trend_str, trend_raw = "—", None
            if len(rows) >= 2:
                prev_net = int(rows[1][comm_long_i] or 0) - int(rows[1][comm_short_i] or 0)
                delta_k  = round((net - prev_net) / 1000, 1)
                arrow    = "↑" if delta_k > 0 else ("↓" if delta_k < 0 else "→")
                trend_str = f"{delta_k:+.1f}K {arrow} (WoW)"
                trend_raw = delta_k

            source_label = "Nasdaq Data Link (CFTC/ES_FO_L_ALL)"
            return _build_cot_result(net_k, short_k, report_date,
                                     trend_str, trend_raw, source_label)
        except Exception as e1:
            pass  # fallback về FinFutWk.txt

    # ── Nguồn 2: CFTC FinFutWk.txt (fallback) ─────────────────────
    try:
        url = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
        resp = requests.get(url, timeout=25,
                            headers={"User-Agent": "python-requests/2.31.0",
                                     "Accept": "text/plain,*/*"})
        resp.raise_for_status()

        reader = csv.reader(io.StringIO(resp.text))
        rows   = [r for r in reader if r and "S&P 500 Consolidated" in r[0]]
        if not rows:
            reader2 = csv.reader(io.StringIO(resp.text))
            rows    = [r for r in reader2 if r and "S&P 500" in r[0]
                       and "E-MINI" not in r[0].upper() and len(r) > 13]
        if not rows:
            raise ValueError("Không tìm thấy S&P 500 trong FinFutWk.txt")

        row         = rows[0]
        report_date = row[2].strip()
        dealer_long  = int(row[8].strip().replace(",", ""))
        dealer_short = int(row[9].strip().replace(",", ""))
        net_k        = round((dealer_long - dealer_short) / 1000, 1)
        short_k      = round(dealer_short / 1000, 1)

        # WoW từ cot_history
        hist = _load_cot_history()
        trend_str, trend_raw = "—", None
        if len(hist) >= 2:
            prev_net  = hist[-2].get("net", net_k)
            delta_k   = round(net_k - prev_net, 1)
            arrow     = "↑" if delta_k > 0 else ("↓" if delta_k < 0 else "→")
            trend_str = f"{delta_k:+.1f}K {arrow} (WoW)"
            trend_raw = delta_k

        source_label = "CFTC FinFutWk.txt (Dealers proxy)"
        return _build_cot_result(net_k, short_k, report_date,
                                 trend_str, trend_raw, source_label)

    except Exception as e2:
        return {
            "category": "Dòng tiền tổ chức",
            "indicator": "COT — Commercial Net",
            "value": "N/A", "trend": "—", "trend_raw": None,
            "threshold": "Short > 70% đỉnh lịch sử",
            "status": "success", "statusLabel": "Bình thường",
            "source": "CFTC / Nasdaq Data Link",
            "link": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
            "note": f"Cả 2 nguồn đều lỗi: {e2}",
            "_meta": {"net_k": None, "short_ratio": None}
        }


def _build_cot_result(net_k, short_k, report_date, trend_str, trend_raw, source_label):
    """Helper: lưu history, tính shortRatio, trả về dict chuẩn."""
    _save_cot_history(net_k, short_k)
    hist_max    = _get_historical_max_short()
    short_ratio = round(abs(net_k) / hist_max, 3) if (net_k < 0 and hist_max > 0) else 0.0
    status, label = evaluate("cot_net", short_ratio)
    ratio_pct   = f"{short_ratio*100:.0f}% của đỉnh lịch sử ({hist_max:.0f}K)"
    value_str   = f"{net_k:+.1f}K contracts — {ratio_pct} ({report_date})"
    return {
        "category":    "Dòng tiền tổ chức",
        "indicator":   "COT — Commercial Net",
        "value":       value_str,
        "trend":       trend_str,
        "trend_raw":   trend_raw,
        "threshold":   "Short > 70% đỉnh lịch sử",
        "status":      status,
        "statusLabel": label,
        "source":      source_label,
        "link":        "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
        "note":        "Commercial net = long − short. shortRatio = |net| / rolling-max-short (104 tuần).",
        "_meta":       {"net_k": net_k, "short_ratio": short_ratio}
    }


def _load_etf_history():
    if os.path.exists(ETF_HISTORY):
        with open(ETF_HISTORY, encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_etf_history(data):
    with open(ETF_HISTORY, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _get_spy_implied_shares(spy_price: float):
    """
    Tính implied shares của SPY từ SPDR daily holdings xlsx.
    AUM = median(shares_held_i × close_price_i / weight_i%) cho top 5 holdings.
    implied_shares = AUM / spy_price
    """
    try:
        import io, statistics
        url = ("https://www.ssga.com/us/en/intermediary/etfs/library-content"
               "/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx")
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if resp.status_code != 200:
            return None

        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        # Tìm ngày holdings từ row "As of DD-Mon-YYYY"
        holdings_date = None
        data_start = 5  # mặc định
        for i, row in enumerate(rows[:8]):
            if row and isinstance(row[1], str) and "As of" in str(row[1]):
                # parse "As of 07-Apr-2026" → "2026-04-07"
                try:
                    import datetime as _dt
                    date_part = str(row[1]).replace("As of ", "").strip()
                    holdings_date = _dt.datetime.strptime(date_part, "%d-%b-%Y").strftime("%Y-%m-%d")
                except Exception:
                    pass
            # Header row chứa "Name", "Ticker", "Weight"
            if row and row[0] == "Name":
                data_start = i + 1
                break

        # Lấy top 5 holdings (ticker, weight%, shares_held)
        holdings = []
        for row in rows[data_start:data_start + 5]:
            if not row or row[0] is None:
                break
            ticker  = row[1]   # e.g. "NVDA"
            weight  = row[4]   # e.g. 7.635363
            shares  = row[6]   # e.g. 283679859.0
            if ticker and weight and shares and weight > 0:
                holdings.append((str(ticker), float(weight), float(shares)))

        if not holdings:
            return None

        # Lấy giá đóng cửa của từng holding vào ngày holdings_date
        tickers_str = " ".join(h[0] for h in holdings)
        period = "5d"
        aum_estimates = []
        for ticker, weight_pct, shares_held in holdings:
            try:
                hist = yf.Ticker(ticker).history(period=period)["Close"]
                if hist.empty:
                    continue
                if holdings_date:
                    # Tìm close price gần nhất với holdings_date
                    dates_str = [str(d)[:10] for d in hist.index]
                    if holdings_date in dates_str:
                        idx = dates_str.index(holdings_date)
                        close = float(hist.iloc[idx])
                    else:
                        close = float(hist.iloc[-1])
                else:
                    close = float(hist.iloc[-1])
                aum_est = shares_held * close / (weight_pct / 100)
                aum_estimates.append(aum_est)
            except Exception:
                continue

        if not aum_estimates:
            return None

        aum = statistics.median(aum_estimates)
        return aum / spy_price if spy_price > 0 else None

    except Exception:
        return None


def fetch_etf_flows():
    """
    ETF Flows — net creation/redemption SPY + QQQ.
    SPY: implied shares từ SPDR daily holdings xlsx (State Street).
    QQQ: implied shares = totalAssets / last_price (yfinance).
    Lưu snapshot hàng ngày, tính Δimplied_shares × price = flow (tỷ USD).
    """
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=7))
    ).strftime("%Y-%m-%d")

    hist    = _load_etf_history()
    total_b = None
    parts   = []

    etf_configs = [
        ("SPY", "spdr_xlsx"),
        ("QQQ", "total_assets"),
    ]

    for sym, method in etf_configs:
        try:
            tk    = yf.Ticker(sym)
            fi    = tk.fast_info
            price = fi.last_price
            if not price:
                continue

            # Lấy implied shares theo từng phương pháp
            if method == "spdr_xlsx":
                implied = _get_spy_implied_shares(price)
            else:  # total_assets
                total_assets = tk.info.get("totalAssets")
                implied = (total_assets / price) if total_assets else None

            if implied is None:
                continue

            # Lưu snapshot hôm nay
            entries = hist.get(sym, [])
            if not isinstance(entries, list):
                entries = []
            snapshot = {"date": today, "implied_shares": implied, "price": price}
            if not entries or entries[-1].get("date") != today:
                entries.append(snapshot)
            else:
                entries[-1] = snapshot
            hist[sym] = entries[-10:]

            # Cần ít nhất 2 ngày để tính delta
            if len(entries) < 2:
                continue

            old       = entries[0]
            price_avg = (price + old.get("price", price)) / 2
            delta     = implied - old["implied_shares"]
            flow_b    = round(delta * price_avg / 1e9, 2)

            if total_b is None:
                total_b = 0.0
            total_b += flow_b
            days = len(entries) - 1
            parts.append(f"{sym}: {flow_b:+.2f}B/{days}d")

        except Exception:
            continue

    _save_etf_history(hist)

    status, label = evaluate("etf_flow", total_b if total_b is not None else 0)

    if total_b is not None:
        arrow     = "↑" if total_b > 0 else ("↓" if total_b < 0 else "→")
        value_str = f"{total_b:+.2f}B USD ({', '.join(parts)})"
        trend_str = f"{total_b:+.2f}B {arrow}"
    else:
        value_str = "Đang tích lũy (~2 ngày để có baseline)"
        trend_str = "N/A"

    return {
        "category": "",
        "indicator": "ETF Flows (SPY+QQQ)",
        "value": value_str,
        "trend": trend_str,
        "trend_raw": total_b,
        "threshold": "Outflow > −2B USD/7d",
        "status": status,
        "statusLabel": label,
        "source": "SPDR holdings xlsx (SPY) + Yahoo Finance (QQQ)",
        "link": "https://etf.com/etfanalytics/etf-fund-flows-tool",
        "note": "SPY: implied shares từ SPDR daily holdings. QQQ: totalAssets/price. Cần 2+ ngày snapshot.",
        "_meta": {"flow_b": total_b}
    }


def _load_naaim_history():
    if os.path.exists(NAAIM_HISTORY):
        with open(NAAIM_HISTORY, encoding="utf-8") as f:
            return json.load(f)
    return []

def _save_naaim_history(exposure):
    hist = _load_naaim_history()
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%Y-%m-%d")
    if hist and hist[-1]["date"] == today:
        hist[-1]["exposure"] = exposure
    else:
        hist.append({"date": today, "exposure": exposure})
    hist = hist[-12:]  # giữ ~3 tháng (12 tuần)
    with open(NAAIM_HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

def _fetch_naaim_exposure():
    """
    NAAIM Exposure Index.
    Nguồn chính: Stooq weekly CSV (đáng tin, không bị block).
    Fallback: scrape naaim.org với plain-text search.
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    # Nguồn 1: Stooq NAAIM weekly CSV — reliable, không cần parse HTML
    try:
        r = requests.get("https://stooq.com/q/d/l/?s=naaim.w&i=w",
                         timeout=15, headers=headers)
        if r.ok and len(r.text) > 50:
            lines = [l.strip() for l in r.text.strip().split("\n")
                     if l.strip() and not l.startswith("Date")]
            if lines:
                cols = lines[-1].split(",")
                if len(cols) >= 5:
                    val = float(cols[4])   # Close column
                    if 0 <= val <= 200:
                        return val
    except Exception:
        pass

    # Nguồn 2: naaim.org — strip HTML → plain text → tìm số
    for url in [
        "https://www.naaim.org/programs/naaim-exposure-index/",
        "https://www.naaim.org/resources/naaim-exposure-index/",
    ]:
        try:
            resp = requests.get(url, timeout=20, headers=headers)
            if not resp.ok:
                continue
            # Strip tags → plain text
            plain = _re.sub(r'<[^>]+>', ' ', resp.text)
            plain = _re.sub(r'&[a-zA-Z]+;', ' ', plain)
            plain = _re.sub(r'\s+', ' ', plain)

            # Tìm "this week" → lấy số gần nhất
            pos = plain.lower().find("this week")
            if pos >= 0:
                snippet = plain[pos:pos+300]
                nums = _re.findall(r'\b(\d{1,3}\.\d{2})\b', snippet)
                for n in nums:
                    val = float(n)
                    if 0 < val <= 200:
                        return val

            # Tìm bất kỳ số hợp lệ nào gần "exposure" hoặc "naaim"
            pos2 = plain.lower().find("exposure index")
            if pos2 >= 0:
                snippet2 = plain[pos2:pos2+500]
                nums2 = _re.findall(r'\b(\d{1,3}\.\d{2})\b', snippet2)
                for n in nums2:
                    val = float(n)
                    if 0 < val <= 200:
                        return val
        except Exception:
            continue

    raise ValueError("Không parse được NAAIM từ Stooq hoặc naaim.org")

def _fetch_aaii_bull():
    """
    AAII Sentiment Survey — Bull% và Bear%.
    Nguồn chính: Stooq weekly CSV (không bị block 403).
    Fallback: scrape aaii.com sentimentsurvey page.
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    # Nguồn 1: Stooq AAII bull + bear weekly — most reliable
    try:
        rb = requests.get("https://stooq.com/q/d/l/?s=aaiibull.w&i=w",
                          timeout=15, headers=headers)
        rr = requests.get("https://stooq.com/q/d/l/?s=aaiibear.w&i=w",
                          timeout=15, headers=headers)
        if rb.ok and rr.ok:
            bull_lines = [l.strip() for l in rb.text.strip().split("\n")
                          if l.strip() and not l.startswith("Date")]
            bear_lines = [l.strip() for l in rr.text.strip().split("\n")
                          if l.strip() and not l.startswith("Date")]
            if bull_lines and bear_lines:
                b  = bull_lines[-1].split(",")
                br = bear_lines[-1].split(",")
                if len(b) >= 5 and len(br) >= 5:
                    bull = float(b[4])
                    bear = float(br[4])
                    if bull < 2:  bull *= 100
                    if bear < 2: bear *= 100
                    if 1 < bull < 100 and 1 < bear < 100:
                        return round(bull, 1), round(bear, 1)
    except Exception:
        pass

    # Nguồn 2: AAII sentimentsurvey page — strip HTML
    try:
        resp = requests.get(
            "https://www.aaii.com/sentimentsurvey",
            timeout=25,
            headers={**headers,
                     "Accept": "text/html,application/xhtml+xml,*/*",
                     "Referer": "https://www.google.com/"}
        )
        if resp.ok:
            plain = _re.sub(r'<[^>]+>', ' ', resp.text)
            plain = _re.sub(r'&[a-zA-Z]+;', ' ', plain)
            plain = _re.sub(r'\s+', ' ', plain)
            bull_m = _re.search(r'[Bb]ullish\W{0,20}?(\d{1,2}\.\d)\s*%', plain)
            bear_m = _re.search(r'[Bb]earish\W{0,20}?(\d{1,2}\.\d)\s*%', plain)
            if bull_m and bear_m:
                return round(float(bull_m.group(1)), 1), round(float(bear_m.group(1)), 1)
    except Exception:
        pass

    raise ValueError("Không lấy được AAII data từ Stooq hoặc aaii.com")

def fetch_sentiment():
    """
    Institutional vs Retail Sentiment:
    - Institutional: NAAIM Exposure Index (0–200) → normalize về 0–100 làm bull proxy
    - Retail: AAII Bull%
    - Diff = retailBull% − instBull% → diff > 0 = retail lạc quan hơn tổ chức
    """
    naaim_val = None
    aaii_bull = None
    aaii_bear = None
    errors    = []

    try:
        naaim_val = _fetch_naaim_exposure()
        _save_naaim_history(naaim_val)
    except Exception as e:
        errors.append(f"NAAIM: {e}")

    try:
        aaii_bull, aaii_bear = _fetch_aaii_bull()
    except Exception as e:
        errors.append(f"AAII: {e}")

    # Normalize NAAIM → 0–100 (100 = fully invested, 200 = 2× leveraged long)
    inst_bull = round(min(naaim_val, 100), 1) if naaim_val is not None else None

    if inst_bull is not None and aaii_bull is not None:
        diff = round(aaii_bull - inst_bull, 1)
        status, label = evaluate("sentiment_diff", diff)
        value_str = (f"Retail {aaii_bull:.0f}% / Inst {inst_bull:.0f}% → "
                     f"diff {diff:+.0f}pp")
        arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
        trend_str = f"{diff:+.0f}pp {arrow}"
        trend_raw = diff
        note = ("Diff = retailBull% − instBull%. Dương cao = retail quá lạc quan vs tổ chức → "
                "contrarian bearish signal.")
    elif aaii_bull is not None:
        # Chỉ có AAII
        spread = round(aaii_bull - (aaii_bear or 0), 1)
        status, label = evaluate("sentiment_diff", spread if spread > 0 else 0)
        value_str = f"AAII Bull {aaii_bull:.0f}% / Bear {aaii_bear:.0f}% (NAAIM N/A)"
        trend_str, trend_raw = "—", None
        note = "NAAIM không lấy được. Chỉ dùng AAII Bull−Bear spread làm proxy."
    else:
        status, label = "success", "Bình thường"
        value_str = "N/A"
        trend_str, trend_raw = "—", None
        note = f"Không lấy được dữ liệu: {'; '.join(errors)}"

    return {
        "category": "",
        "indicator": "Sentiment (NAAIM vs AAII)",
        "value": value_str,
        "trend": trend_str,
        "trend_raw": trend_raw,
        "threshold": "Retail − Inst > +25pp",
        "status": status,
        "statusLabel": label,
        "source": "NAAIM Exposure Index · AAII Sentiment Survey",
        "link": "https://www.naaim.org/resources/naaim-exposure-index/",
        "note": note,
        "_meta": {
            "naaim": naaim_val,
            "inst_bull": inst_bull,
            "aaii_bull": aaii_bull,
            "aaii_bear": aaii_bear,
        }
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

def fetch_dxy():
    """
    US Dollar Index (DXY) — sức mạnh đồng USD.
    Ticker: DX-Y.NYB hoặc DX=F (futures) trên Yahoo Finance.
    DXY tăng mạnh → rủi ro tài sản rủi ro tăng (liquidity squeeze, EM stress).
    """
    hist = get_history("DX-Y.NYB")
    price = get_price("DX-Y.NYB")
    if price is None:
        hist  = get_history("DX=F")
        price = get_price("DX=F")

    chg = week_change(hist)
    status, label = evaluate("dxy", price)

    return {
        "category": "",
        "indicator": "DXY (USD Index)",
        "value": f"{price:.2f}" if price else "N/A",
        "trend": fmt_change(chg),
        "trend_raw": chg,
        "threshold": ">107",
        "status": status,
        "statusLabel": label,
        "source": "Yahoo Finance (DX-Y.NYB)",
        "link": "https://finance.yahoo.com/quote/DX-Y.NYB/",
        "note": "US Dollar Index — DXY tăng mạnh >107 = USD siết chặt thanh khoản, rủi ro tài sản rủi ro tăng.",
        "_meta": {"dxy": price}
    }

# ===== RISK SCORE ENGINE v2 =====
# Base score (weighted groups) × Lead Multiplier → Final score 0–100

def _get_num(s):
    """Lấy số đầu tiên từ string (hỗ trợ dấu +/-)."""
    nums = _re.findall(r"[-+]?\d+\.?\d*", str(s))
    return float(nums[0]) if nums else None

# --- Scoring functions (theo logic document) ---

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

def _hormuz_score(value_str, status_key=None):
    """
    Ưu tiên status_key từ _meta (RSS auto), fallback parse string thủ công.
    none=0, tension=4, partial_blockade=7, full_blockade=10
    """
    if status_key:
        return {"none": 0, "tension": 4, "partial_blockade": 7, "full_blockade": 10}.get(status_key, 0)
    # Fallback: parse string (tương thích ngược với entry thủ công cũ)
    v = str(value_str).lower()
    if ("phong tỏa" in v or "phông tỏa" in v) and "chưa" not in v:
        if "toàn bộ" in v or "hoàn toàn" in v: return 10
        return 7
    if "căng thẳng" in v or "tension" in v: return 4
    return 0

def _cot_score(short_ratio):
    """shortRatio = |net| / historicalMaxShort. Theo getCOTScore()."""
    if short_ratio is None: return 2
    if short_ratio <= 0:    return 0
    if short_ratio < 0.3:   return 2
    if short_ratio < 0.5:   return 4
    if short_ratio < 0.7:   return 6
    if short_ratio < 0.9:   return 8
    return 10

def _etf_flow_score(flow_b):
    """flow_b: tỷ USD 7 ngày. Theo getETFFlowScore()."""
    if flow_b is None: return 2
    if flow_b > 5:    return 0
    if flow_b > 0:    return 1
    if flow_b > -2:   return 3
    if flow_b > -5:   return 6
    if flow_b > -10:  return 8
    return 10

def _sentiment_score(inst_bull, aaii_bull):
    """diff = retailBull − instBull. Theo getSentimentScore()."""
    if inst_bull is None or aaii_bull is None: return 2
    diff = aaii_bull - inst_bull
    if diff < 5:   return 0
    if diff < 15:  return 3
    if diff < 25:  return 6
    if diff < 35:  return 8
    return 10

def _vix_curve_score(value_str, trend_pct):
    """Theo getVixCurveScore() — map status string."""
    v = str(value_str).lower()
    if   "backwardation mạnh" in v or "deep backwardation" in v: s = 10
    elif "backwardation" in v:                                    s = 8
    elif "phẳng" in v or "flat" in v:                            s = 6
    elif "contango nhẹ" in v or "light contango" in v:           s = 4
    elif "contango" in v:                                         s = 2
    else:                                                         s = 4
    if (trend_pct or 0) > 5 and s == 4: s += 1
    return min(10, max(0, s))

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

def _put_call_score(ratio):
    if ratio is None: return 0
    if ratio < 0.7:   return 0
    if ratio < 0.9:   return 2
    if ratio < 1.1:   return 4
    if ratio < 1.3:   return 7
    return 10

def _hyg_tlt_score(weekly_chg):
    if weekly_chg is None or weekly_chg >= 0: return 0
    decline = abs(weekly_chg)
    if decline < 2:  return 0
    if decline < 5:  return 2
    if decline < 10: return 5
    if decline < 15: return 8
    return 10

def _spread_score(spread, is_expanding, is_inverted):
    """Theo getSpread2s10sScore()."""
    if spread is None: return 0
    if is_inverted and spread < -0.5: return 10
    if is_inverted:                   return 6
    if spread > 0.5 and is_expanding: return 0
    if spread > 0.5:                  return 1
    if spread > 0:                    return 3
    return 0

def _dxy_score(dxy, trend_pct):
    """Theo getDXYScore()."""
    if dxy is None: return 0
    if dxy < 100:   s = 0
    elif dxy < 103: s = 2
    elif dxy < 105: s = 4
    elif dxy < 107: s = 6
    elif dxy < 110: s = 8
    else:           s = 10
    if (trend_pct or 0) > 2: s += 1
    return min(10, max(0, s))

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

# --- Lead Multiplier ---

def _calc_lead_multiplier(lead_meta):
    """
    Khuếch đại điểm khi có lead indicators kích hoạt. Tối đa ×2.0.
    Cấp 1 +0.25: COT shortRatio > 0.7, VIX backwardation
    Cấp 2 +0.15: Oil > $100, 2s10s đảo ngược
    Cấp 3 +0.10: ETF outflow > $5B, retail − inst > 20pp
    """
    mult = 1.0
    leads = []

    if (lead_meta.get("short_ratio") or 0) > 0.7:
        mult += 0.25
        leads.append("COT short ròng > 70% đỉnh lịch sử")

    if "backwardation" in (lead_meta.get("vix_curve_str") or "").lower():
        mult += 0.25
        leads.append("VIX futures curve: Backwardation")

    if (lead_meta.get("oil_price") or 0) > 100:
        mult += 0.15
        leads.append("Dầu WTI > $100/thùng")

    if lead_meta.get("spread_inverted", False):
        mult += 0.15
        leads.append("2s10s spread đảo ngược")

    if (lead_meta.get("etf_flow_b") or 0) < -5:
        mult += 0.10
        leads.append("ETF outflow > $5B/7d")

    diff = lead_meta.get("sentiment_diff")
    if diff is not None and diff > 20:
        mult += 0.10
        leads.append(f"Retail lạc quan hơn tổ chức ({diff:+.0f}pp)")

    return round(min(mult, 2.0), 2), leads

# --- Main calc ---

def calc_risk_score(indicators):
    """
    Risk Score v2 với lead multiplier.
    Base groups (thang 0–10):
      geo    15% : oil×0.6  + hormuz×0.4
      inst   25% : cot×0.4  + etf×0.3   + sentiment×0.3
      market 40% : vixCurve×0.35 + vix×0.25 + putCall×0.20 + hygTlt×0.20
      macro  20% : spread×0.40 + dxy×0.30 + yield10y×0.30
    Final = base_10 × multiplier × 10 → clamp 0–100
    Levels: ≤35 Normal, ≤55 Caution, ≤75 High Alert, >75 Systemic
    """
    vals = {ind["indicator"]: ind for ind in indicators}
    def v(name):    return vals.get(name, {})
    def tr(name):   return v(name).get("trend_raw") or 0
    def meta(name): return v(name).get("_meta", {})

    # Extract raw values
    oil_price    = _get_num(v("Dầu WTI").get("value", ""))
    vix_val      = _get_num(v("VIX").get("value", ""))
    y10_val      = _get_num(v("10-year yield").get("value", ""))
    pc_val       = _get_num(v("Put/Call ratio").get("value", ""))
    dxy_val      = meta("DXY (USD Index)").get("dxy") or _get_num(v("DXY (USD Index)").get("value", ""))

    # COT shortRatio từ _meta
    short_ratio  = meta("COT — Commercial Net").get("short_ratio")

    # ETF flows tỷ USD từ _meta
    etf_flow_b   = meta("ETF Flows (SPY+QQQ)").get("flow_b")

    # Sentiment: inst_bull + aaii_bull từ _meta
    sent_meta    = meta("Sentiment (NAAIM vs AAII)")
    inst_bull    = sent_meta.get("inst_bull")
    aaii_bull    = sent_meta.get("aaii_bull")
    sent_diff    = round(aaii_bull - inst_bull, 1) if (inst_bull is not None and aaii_bull is not None) else None

    # 2s10s spread
    spread_str   = v("2s10s spread").get("value", "")
    spread_num   = _get_num(spread_str)
    spread_chg   = tr("2s10s spread")
    is_inverted  = (spread_num is not None and spread_num < 0)
    is_expanding = (spread_chg or 0) > 0

    vix_curve_str = v("VIX futures curve").get("value", "")

    # Scores
    oil_s    = _oil_score(oil_price, tr("Dầu WTI"))
    hormuz_meta = meta("Xung đột Hormuz")
    hormuz_s = _hormuz_score(
        v("Xung đột Hormuz").get("value", ""),
        status_key=hormuz_meta.get("status_key")
    )
    cot_s    = _cot_score(short_ratio)
    etf_s    = _etf_flow_score(etf_flow_b)
    sent_s   = _sentiment_score(inst_bull, aaii_bull)
    curve_s  = _vix_curve_score(vix_curve_str, tr("VIX futures curve"))
    vix_s    = _vix_score(vix_val, tr("VIX"))
    pc_s     = _put_call_score(pc_val)
    hyg_s    = _hyg_tlt_score(tr("HYG/TLT ratio"))
    sp_s     = _spread_score(spread_num, is_expanding, is_inverted)
    dxy_s    = _dxy_score(dxy_val, tr("DXY (USD Index)"))
    y10_s    = _yield_score(y10_val, tr("10-year yield"))

    # Group scores
    geo_score    = oil_s  * 0.6  + hormuz_s * 0.4
    inst_score   = cot_s  * 0.4  + etf_s    * 0.3  + sent_s  * 0.3
    market_score = curve_s * 0.35 + vix_s   * 0.25 + pc_s    * 0.20 + hyg_s * 0.20
    macro_score  = sp_s   * 0.40  + dxy_s   * 0.30  + y10_s  * 0.30

    # Base score (0–10)
    base_10 = (geo_score    * 0.15 +
               inst_score   * 0.25 +
               market_score * 0.40 +
               macro_score  * 0.20)

    # Lead multiplier
    lead_meta = {
        "short_ratio":     short_ratio,
        "vix_curve_str":   vix_curve_str,
        "oil_price":       oil_price,
        "spread_inverted": is_inverted,
        "etf_flow_b":      etf_flow_b,
        "sentiment_diff":  sent_diff,
    }
    multiplier, active_leads = _calc_lead_multiplier(lead_meta)

    # Final
    total      = int(round(min(base_10 * multiplier * 10, 100)))
    base_score = int(round(min(base_10 * 10, 100)))

    if total <= 35:   level, color = "BÌNH THƯỜNG",    "success"
    elif total <= 55: level, color = "CẢNH GIÁC",       "warning"
    elif total <= 75: level, color = "CẢNH BÁO CAO",    "danger"
    else:             level, color = "RỦI RO HỆ THỐNG", "critical"

    return {
        "score":        total,
        "base_score":   base_score,
        "multiplier":   multiplier,
        "level":        level,
        "color":        color,
        "active_leads": active_leads,
        "breakdown": {
            "geo":    round(geo_score    * 10, 1),
            "inst":   round(inst_score   * 10, 1),
            "market": round(market_score * 10, 1),
            "macro":  round(macro_score  * 10, 1),
        },
        "indicator_scores": {
            "oil": round(oil_s,2), "hormuz": round(hormuz_s,2),
            "cot": round(cot_s,2), "etf_flow": round(etf_s,2), "sentiment": round(sent_s,2),
            "vix_curve": round(curve_s,2), "vix": round(vix_s,2),
            "put_call": round(pc_s,2), "hyg_tlt": round(hyg_s,2),
            "spread": round(sp_s,2), "dxy": round(dxy_s,2), "yield_10y": round(y10_s,2),
        },
    }


def update_risk_history(risk):
    """Lưu điểm rủi ro vào risk_history.json — mỗi giờ 1 điểm, giữ 720 điểm (30 ngày)."""
    hist = []
    if os.path.exists(RISK_HISTORY):
        with open(RISK_HISTORY, encoding="utf-8") as f:
            hist = json.load(f)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    # Key theo giờ: YYYY-MM-DD HH
    hour_key = now.strftime("%Y-%m-%d %H")
    entry = {
        "date":  now.strftime("%Y-%m-%dT%H:%M"),  # ISO-style, đủ để sort & filter
        "score": risk["score"],
        "level": risk["level"],
    }

    # Nếu đã có entry trong giờ này → overwrite (tránh duplicate)
    if hist and hist[-1]["date"][:13] == hour_key:
        hist[-1] = entry
    else:
        hist.append(entry)

    hist = hist[-720:]  # giữ 30 ngày × 24h = 720 điểm
    with open(RISK_HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    return hist


# ===== EMAIL REPORT =====

def send_email_report(result, risk):
    """
    Gửi báo cáo rủi ro qua email sau mỗi lần cập nhật data.
    Dùng Resend API (resend.com) — miễn phí 100 email/ngày.
    Env vars cần thiết:
      RESEND_API_KEY : API key từ resend.com
      REPORT_EMAIL   : địa chỉ email nhận báo cáo
    """
    RESEND_KEY   = os.environ.get("RESEND_API_KEY", "")
    REPORT_EMAIL = os.environ.get("REPORT_EMAIL", "")

    if not RESEND_KEY or not REPORT_EMAIL:
        return  # Skip nếu chưa config

    score    = risk["score"]
    level    = risk["level"]
    mult     = risk["multiplier"]
    bd       = risk["breakdown"]
    leads    = risk.get("active_leads", [])
    updated  = result["last_updated"]

    # Màu badge theo mức độ
    color_map = {
        "BÌNH THƯỜNG":    "#22c55e",
        "CẢNH GIÁC":      "#f59e0b",
        "CẢNH BÁO CAO":   "#ef4444",
        "RỦI RO HỆ THỐNG":"#a78bfa",
    }
    badge_color = color_map.get(level, "#888")

    # Bảng chỉ báo HTML
    rows_html = ""
    status_color = {"danger":"#ef4444","warning":"#f59e0b","success":"#22c55e"}
    for ind in result["indicators"]:
        sc = status_color.get(ind["status"], "#888")
        rows_html += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #2a2a2a;color:#888;font-size:12px">{ind['indicator']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #2a2a2a;font-family:monospace;font-size:12px">{ind['value'][:60]}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #2a2a2a;text-align:center">
            <span style="background:{sc}22;color:{sc};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{ind['statusLabel']}</span>
          </td>
        </tr>"""

    leads_html = ""
    if leads:
        leads_html = "<br>".join(f"⚡ {l}" for l in leads)
    else:
        leads_html = "<span style='color:#555'>Không có lead indicator kích hoạt</span>"

    html = f"""<!DOCTYPE html>
<html><body style="background:#0a0a0a;color:#e8e8e8;font-family:'Segoe UI',sans-serif;margin:0;padding:0">
<div style="max-width:680px;margin:0 auto;padding:24px">

  <!-- Header -->
  <div style="background:#141414;border:1px solid #242424;border-radius:12px;padding:24px;margin-bottom:16px;text-align:center">
    <div style="font-size:13px;color:#888;margin-bottom:8px">📊 Market Monitor · {updated}</div>
    <div style="font-size:64px;font-weight:800;color:{badge_color};line-height:1">{score}</div>
    <div style="font-size:13px;color:#555;margin-bottom:12px">/100</div>
    <div style="display:inline-block;background:{badge_color}22;color:{badge_color};padding:6px 20px;border-radius:6px;font-weight:700;font-size:14px;border:1px solid {badge_color}55">{level}</div>
    <div style="margin-top:10px;color:#888;font-size:12px">Hệ số khuếch đại: ×{mult}</div>
  </div>

  <!-- Breakdown -->
  <div style="background:#141414;border:1px solid #242424;border-radius:12px;padding:20px;margin-bottom:16px">
    <div style="font-size:12px;color:#555;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px">Phân loại rủi ro</div>
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <td style="padding:6px 0;color:#888;font-size:13px">Địa chính trị (15%)</td>
        <td style="text-align:right;font-weight:700;color:{'#ef4444' if bd['geo']>=70 else '#f59e0b' if bd['geo']>=50 else '#22c55e'}">{bd['geo']}/100</td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:#888;font-size:13px">Dòng tiền tổ chức (25%)</td>
        <td style="text-align:right;font-weight:700;color:{'#ef4444' if bd['inst']>=70 else '#f59e0b' if bd['inst']>=50 else '#22c55e'}">{bd['inst']}/100</td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:#888;font-size:13px">Thị trường (40%)</td>
        <td style="text-align:right;font-weight:700;color:{'#ef4444' if bd['market']>=70 else '#f59e0b' if bd['market']>=50 else '#22c55e'}">{bd['market']}/100</td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:#888;font-size:13px">Vĩ mô (20%)</td>
        <td style="text-align:right;font-weight:700;color:{'#ef4444' if bd['macro']>=70 else '#f59e0b' if bd['macro']>=50 else '#22c55e'}">{bd['macro']}/100</td>
      </tr>
    </table>
  </div>

  <!-- Lead indicators -->
  <div style="background:#1a1200;border:1px solid #f59e0b33;border-radius:12px;padding:16px;margin-bottom:16px;font-size:13px;color:#f59e0b">
    {leads_html}
  </div>

  <!-- Indicators table -->
  <div style="background:#141414;border:1px solid #242424;border-radius:12px;overflow:hidden;margin-bottom:16px">
    <table style="width:100%;border-collapse:collapse">
      <thead>
        <tr style="background:#1a1a1a">
          <th style="padding:10px 12px;text-align:left;font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.08em">Chỉ báo</th>
          <th style="padding:10px 12px;text-align:left;font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.08em">Giá trị</th>
          <th style="padding:10px 12px;text-align:center;font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.08em">Trạng thái</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <!-- Footer -->
  <div style="text-align:center;font-size:11px;color:#444;padding-top:8px">
    <a href="https://market-monitor-kappa.vercel.app/" style="color:#60a5fa;text-decoration:none">Xem dashboard →</a>
    &nbsp;·&nbsp; Market Monitor by @Hirohnguyen
  </div>

</div>
</body></html>"""

    subject_icon = "🟢" if score<=35 else "🟡" if score<=55 else "🔴" if score<=75 else "🟣"
    subject = f"{subject_icon} Market Monitor: {score}/100 — {level} ({updated[:5]})"

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "from":    "Market Monitor <onboarding@resend.dev>",
                "to":      [REPORT_EMAIL],
                "subject": subject,
                "html":    html,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            print(f"[Email] Sent to {REPORT_EMAIL} — {subject}")
        else:
            print(f"[Email] Error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[Email] Exception: {e}")


# ===== MAIN =====

def main():
    print("Đang fetch dữ liệu...")

    vix_row, vix_curve_row = fetch_vix()

    indicators = [
        # 1. Địa chính trị
        fetch_wti(),
        fetch_hormuz(),
        # 2. Dòng tiền tổ chức
        fetch_cot(),
        fetch_etf_flows(),
        fetch_sentiment(),
        # 3. Thị trường
        vix_row,
        vix_curve_row,
        fetch_hyg_tlt(),
        fetch_put_call(),
        # 4. Vĩ mô
        fetch_yield_10y(),
        fetch_spread_2s10s(),
        fetch_dxy(),
    ]

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    result = {
        "last_updated": now.strftime("%H:%M %A, %d/%m/%Y (GMT+7)"),
        "indicators": indicators
    }

    risk = calc_risk_score(indicators)
    update_risk_history(risk)
    result["risk"] = risk

    def _sanitize(obj):
        """Đệ quy thay NaN/Inf → None để đảm bảo JSON hợp lệ."""
        import math
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(_sanitize(result), f, ensure_ascii=False, indent=2)

    bd = risk["breakdown"]
    print(f"Saved → {OUTPUT}")
    print(f"last_updated: {result['last_updated']}")
    print(f"Risk score: {risk['score']}/100  base={risk['base_score']} ×{risk['multiplier']}  ({risk['level']})")
    print(f"Breakdown: geo={bd['geo']} inst={bd['inst']} market={bd['market']} macro={bd['macro']}")
    if risk.get("active_leads"):
        print(f"Active leads: {', '.join(risk['active_leads'])}")
    for ind in indicators:
        meta_str = ""
        if "_meta" in ind:
            m = ind["_meta"]
            if "short_ratio" in m and m["short_ratio"] is not None:
                meta_str = f" [shortRatio={m['short_ratio']:.2f}]"
            elif "flow_b" in m and m["flow_b"] is not None:
                meta_str = f" [flow={m['flow_b']:+.2f}B]"
            elif "naaim" in m and m["naaim"] is not None:
                meta_str = f" [NAAIM={m['naaim']:.1f}]"
        print(f"  [{ind['status']:7}] {ind['indicator']:<32} = {ind['value'][:40]:<40}{meta_str}")

    send_email_report(result, risk)

if __name__ == "__main__":
    main()
