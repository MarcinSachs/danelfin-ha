"""
Test script for Danelfin data parsing.
Usage: python test_danelfin.py [TICKER] [--market us|eu|etf]
Examples:
  python test_danelfin.py NVDA
  python test_danelfin.py SAN.MC --market eu
  python test_danelfin.py BUG --market etf
Default ticker: NVDA, default market: us
"""
from __future__ import annotations

import re
import sys

import requests

MARKET_US = "us"
MARKET_EU = "eu"
MARKET_ETF = "etf"

BASE_URL_MAP = {
    MARKET_US: "https://danelfin.com/stock/{ticker}",
    MARKET_EU: "https://danelfin.com/stock/eu/{ticker}",
    MARKET_ETF: "https://danelfin.com/etf/{ticker}",
}

# Parse CLI args
args = sys.argv[1:]
TICKER = "NVDA"
MARKET = MARKET_US
skip_next = False
for i, arg in enumerate(args):
    if skip_next:
        skip_next = False
        continue
    if arg == "--market" and i + 1 < len(args):
        MARKET = args[i + 1].lower()
        skip_next = True
    elif not arg.startswith("--"):
        TICKER = arg.upper()

if MARKET not in BASE_URL_MAP:
    print(f"ERROR: unknown market '{MARKET}'. Use: us, eu, etf")
    sys.exit(1)

URL = BASE_URL_MAP[MARKET].format(ticker=TICKER)
IS_ETF = (MARKET == MARKET_ETF)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def safe_float(v: str) -> float | None:
    try:
        return float(v.replace(",", "").replace("+", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def safe_int(v: str) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse(html: str, ticker: str, is_etf: bool = False) -> dict:
    result: dict = {"ticker": ticker}

    # ── Company name ─────────────────────────────────────────────────────────
    # <span class="TickerName_company__XXXX">NVIDIA Corp</span>
    m = re.search(r'class="[^"]*TickerName_company[^"]*"[^>]*>([^<]+)<', html)
    if m:
        result["company_name"] = m.group(1).strip()

    # ── AI Score (main gauge) ────────────────────────────────────────────────
    # Inside AiScoreCard_wrapper the aria-label is in RSC payload as:
    #   \"aria-label\":\"N out of 10\"
    # or in rendered HTML as: aria-label="N out of 10"
    ai_card = re.search(r'AiScoreCard_wrapper', html)
    if ai_card:
        snippet = html[ai_card.start(): ai_card.start() + 5000]
        # Handle both RSC escaped (\"aria-label\":\"N out of 10\")
        # and rendered HTML (aria-label="N out of 10")
        m = re.search(r'aria-label[=:\\"]+?(\d+) out of 10', snippet)
        if m:
            result["ai_score"] = safe_int(m.group(1))

    # ── Rating label ─────────────────────────────────────────────────────────
    # <span class="AiScoreCard_actionText__XXXX ...">Buy</span>
    m = re.search(
        r'class="[^"]*AiScoreCard_actionText[^"]*"[^>]*>([^<]+)<', html
    )
    if m:
        result["rating"] = m.group(1).strip()

    # ── Sub-scores: Fundamental / Technical / Sentiment / Low Risk ───────────
    # Anchor to the <ul> list first to avoid matching AI Score card or RSC payload.
    # Structure per <li>:
    #   <div role="img" aria-label="N out of 10"> ... </div><span>Label</span>
    LABEL_MAP = {
        "fundamental": "fundamental_score",
        "technical": "technical_score",
        "sentiment": "sentiment_score",
        "low risk": "risk_score",
    }
    # AiScoreBreakdown_scoreList appears multiple times: first as a loading
    # skeleton, later in RSC payload (escaped JSON) and rendered HTML.
    # Normalize escaped quotes in every chunk so the aria-label regex works
    # regardless of which occurrence we land on.
    _BSLASH_QUOTE = chr(92) + chr(34)
    for bd_m in re.finditer(r'AiScoreBreakdown_scoreList', html):
        ul_end = html.find('</ul>', bd_m.start())
        raw_chunk = html[bd_m.start(
        ): ul_end] if ul_end > 0 else html[bd_m.start(): bd_m.start() + 15000]
        chunk = raw_chunk.replace(_BSLASH_QUOTE, chr(34))
        if 'aria-label' not in chunk:
            continue
        for m in re.finditer(
            r'aria-label="(\d+) out of 10".*?<span>([^<]+)</span>',
            chunk,
            re.DOTALL,
        ):
            label = m.group(2).strip().lower()
            key = LABEL_MAP.get(label)
            if key:
                result[key] = safe_int(m.group(1))
        if any(k in result for k in LABEL_MAP.values()):
            break  # found real data, stop

    # ── Price (from RSC payload) ─────────────────────────────────────────────
    # TickerPrice_price appears multiple times (CSS rules, RSC payload, etc.).
    # Iterate all occurrences and use the first window that has a "value" field.
    for pm in re.finditer(r'TickerPrice_price', html):
        window = html[pm.start(): pm.start() +
                      400].replace(_BSLASH_QUOTE, chr(34))
        vm = re.search(r'"value"\s*:\s*([\d.]+)', window)
        if vm:
            result["price"] = safe_float(vm.group(1))
            cm = re.search(r'"currency"\s*:\s*"([A-Z]+)', window)
            result["currency"] = cm.group(1) if cm else "USD"
            break

    # ── Probability advantage ─────────────────────────────────────────────────
    # <div class="AIScoreAlphaFactors_probabilityAdvantage__XXXX">
    #   <p ...>NVDA probability advantage ...</p>
    #   <span ...>+6.99%</span>
    m = re.search(
        r'AIScoreAlphaFactors_probabilityAdvantage[^"]*"'
        r'.*?PercentageDisplay_percentageDisplay[^"]*"[^>]*>'
        r'([+-]?\d+\.?\d*)\s*%',
        html,
        re.DOTALL,
    )
    if m:
        result["probability_advantage"] = safe_float(m.group(1))
    else:
        # Fallback: text pattern (ETFs use a different component/layout)
        adv_target = r'the ETF universe' if is_etf else r'the market'
        fb = re.search(
            rf'{re.escape(ticker)}\s+probability advantage of beating\s+{adv_target}'
            r'.*?\(3M\).*?([+-]\d+\.?\d*)\s*%',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if fb:
            result["probability_advantage"] = safe_float(fb.group(1))
    # ── Probability of beating the market / ETF universe (3M) ───────────────
    beat_target = r'the ETF universe' if is_etf else r'the market'
    m = re.search(
        rf'{re.escape(ticker)}\s+probability of beating\s+{beat_target}[^(]*\(3M\)'
        r'</span>.*?<span[^>]*PercentageDisplay[^>]*>([\d.]+)\s*%',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        result["beat_market_prob"] = safe_float(m.group(1))

    return result


def main() -> None:
    print(f"Fetching {URL} ...")
    try:
        r = requests.get(URL, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"HTTP {r.status_code}  |  size={len(r.text):,} bytes")
    if r.status_code != 200:
        print("Unexpected status code.")
        sys.exit(1)

    data = parse(r.text, TICKER, is_etf=IS_ETF)

    print()
    print(f"{'─' * 40}")
    print(f"  Danelfin data for: {TICKER} [{MARKET.upper()}]")
    print(f"{'─' * 40}")

    LABELS = {
        "ticker":               "Ticker",
        "company_name":         "Company name",
        "ai_score":             "AI Score (1-10)",
        "rating":               "Rating",
        "fundamental_score":    "Fundamental score",
        "technical_score":      "Technical score",
        "sentiment_score":      "Sentiment score",
        "risk_score":           "Low Risk score",
        "price":                "Price",
        "currency":             "Currency",
        "beat_market_prob":     "Beat market/ETF-universe prob (%)",
        "probability_advantage": "Probability advantage (%)",
    }

    for key, label in LABELS.items():
        value = data.get(key)
        status = "✓" if value is not None else "✗ MISSING"
        print(f"  {label:<30} {status}  {'' if value is None else value}")

    print()
    missing = [k for k in LABELS if data.get(k) is None]
    if missing:
        print(f"WARNING: missing fields: {missing}")
    else:
        print("All fields found successfully!")


if __name__ == "__main__":
    main()
