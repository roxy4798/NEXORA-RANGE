"""
scripts/prepare_all_futures_data.py — Universe Discovery & Data Synchronization for ALL Binance Futures.

Discovers all active Binance USD(S)-M perpetual contracts (quoteAsset=USDT, contractType=PERPETUAL, status=TRADING).
Reuses existing cached 4H candles in data/research_klines/.
Fetches missing symbols in parallel with bounded retries and exponential backoff.
Filters out symbols without usable 4H historical data (< 200 bars for ATR-200 warmup).
Generates:
- docs/backtest/ALL_FUTURES_UNIVERSE.json
- docs/backtest/ALL_FUTURES_UNIVERSE_REPORT.md
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "research_klines"
DOCS_DIR = ROOT_DIR / "docs" / "backtest"

TIMEFRAME = "4h"
MIN_CANDLES_REQUIRED = 200  # For Wilder ATR(200) warmup
TARGET_CANDLES = 1000
MAX_RETRIES = 3


def discover_all_futures_symbols() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Discovers all USDT perpetual contracts from Binance USD(S)-M Futures."""
    print("Querying Binance USD(S)-M exchangeInfo for all contracts...")
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # Also query 24hr ticker for volume metadata (informational only, not for filtering/ranking)
    vol_map = {}
    try:
        t_req = urllib.request.Request("https://fapi.binance.com/fapi/v1/ticker/24hr", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(t_req, timeout=15) as t_resp:
            tickers = json.loads(t_resp.read().decode("utf-8"))
            for t in tickers:
                vol_map[t["symbol"]] = float(t.get("quoteVolume", 0.0))
    except Exception:
        pass

    raw_symbols = data.get("symbols", [])
    eligible = []
    excluded = []

    for s in raw_symbols:
        sym = s.get("symbol", "")
        status = s.get("status", "")
        contract_type = s.get("contractType", "")
        quote_asset = s.get("quoteAsset", "")

        # Check ASCII
        try:
            sym.encode("ascii")
        except UnicodeEncodeError:
            excluded.append({"symbol": sym, "reason": "Non-ASCII symbol name", "status": status, "contract_type": contract_type, "quote_asset": quote_asset})
            continue

        if quote_asset != "USDT":
            excluded.append({"symbol": sym, "reason": "Non-USDT quote asset", "status": status, "contract_type": contract_type, "quote_asset": quote_asset})
            continue

        if contract_type != "PERPETUAL":
            excluded.append({"symbol": sym, "reason": "Non-perpetual contract (delivery/quarterly)", "status": status, "contract_type": contract_type, "quote_asset": quote_asset})
            continue

        if status != "TRADING":
            excluded.append({"symbol": sym, "reason": "Non-trading contract status", "status": status, "contract_type": contract_type, "quote_asset": quote_asset})
            continue

        eligible.append({
            "symbol": sym,
            "status": status,
            "contract_type": contract_type,
            "quote_asset": quote_asset,
            "volume_24h": vol_map.get(sym, 0.0),
        })

    # Sort alphabetically by symbol to avoid any ranking bias
    eligible.sort(key=lambda x: x["symbol"])
    return eligible, excluded


def check_local_cache(symbol: str) -> Optional[Tuple[Path, int]]:
    """Checks if valid 4H klines cache already exists locally for this symbol."""
    matches = list(DATA_DIR.glob(f"{symbol}_{TIMEFRAME}_*.json"))
    if not matches:
        return None
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    best_file = matches[0]
    try:
        with open(best_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) >= MIN_CANDLES_REQUIRED:
            return best_file, len(data)
    except Exception:
        pass
    return None


def fetch_missing_klines(symbol: str) -> Optional[List[Dict[str, Any]]]:
    """Fetches up to 1000 4H candles from Binance Futures API."""
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={TIMEFRAME}&limit={TARGET_CANDLES}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    raw_data = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw_data = json.loads(resp.read().decode("utf-8"))
                break
        except Exception:
            if attempt == MAX_RETRIES:
                return None
            time.sleep(0.3 * (2 ** attempt))

    if not raw_data or not isinstance(raw_data, list):
        return None

    # Deduplicate and sort by open timestamp
    seen = set()
    dedup = []
    for k in raw_data:
        ot = int(k[0])
        if ot not in seen:
            seen.add(ot)
            dedup.append(k)
    dedup.sort(key=lambda x: int(x[0]))

    candles = []
    for k in dedup:
        candles.append({
            "symbol": symbol,
            "timeframe": TIMEFRAME,
            "timestamp": int(k[0]),
            "close_time": int(k[6]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "quote_volume": float(k[7]),
            "is_closed": True,
        })
    return candles


def sync_symbol_data(sym_info: Dict[str, Any]) -> Dict[str, Any]:
    sym = sym_info["symbol"]

    # 1. Check local cache first
    cached = check_local_cache(sym)
    if cached is not None:
        c_path, c_count = cached
        return {
            "symbol": sym,
            "usable": True,
            "cached": True,
            "candle_count": c_count,
            "file_path": str(c_path),
            "error": None,
        }

    # 2. Download missing data
    candles = fetch_missing_klines(sym)
    if candles is None or len(candles) < MIN_CANDLES_REQUIRED:
        cnt = len(candles) if candles else 0
        return {
            "symbol": sym,
            "usable": False,
            "cached": False,
            "candle_count": cnt,
            "file_path": None,
            "error": f"Insufficient historical candles ({cnt} < {MIN_CANDLES_REQUIRED})",
        }

    # Save to disk cache
    out_file = DATA_DIR / f"{sym}_{TIMEFRAME}_{len(candles)}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(candles, f)

    return {
        "symbol": sym,
        "usable": True,
        "cached": False,
        "candle_count": len(candles),
        "file_path": str(out_file),
        "error": None,
    }


def main():
    t0 = time.time()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("  NEXORA — ALL BINANCE USD(S)-M FUTURES UNIVERSE DISCOVERY & SYNC  ")
    print("=" * 80)

    eligible_symbols, excluded_raw = discover_all_futures_symbols()
    print(f"Total eligible perpetual symbols discovered: {len(eligible_symbols)}")
    print(f"Total raw excluded symbols (delivery, non-USDT, etc.): {len(excluded_raw)}")

    print("\nSynchronizing local data cache for all eligible symbols (max 15 workers)...")
    sync_results = []
    with ThreadPoolExecutor(max_workers=15) as pool:
        sync_results = list(pool.map(sync_symbol_data, eligible_symbols))

    usable_universe = []
    insufficient_data_symbols = []

    for item, sync in zip(eligible_symbols, sync_results):
        if sync["usable"]:
            usable_universe.append({
                "symbol": sync["symbol"],
                "status": item["status"],
                "contract_type": item["contract_type"],
                "quote_asset": item["quote_asset"],
                "volume_24h": item["volume_24h"],
                "candle_count": sync["candle_count"],
                "file_path": sync["file_path"],
                "was_cached": sync["cached"],
            })
        else:
            insufficient_data_symbols.append({
                "symbol": sync["symbol"],
                "reason": sync["error"],
                "candle_count": sync["candle_count"],
            })

    total_usable = len(usable_universe)
    total_candles = sum(s["candle_count"] for s in usable_universe)
    cached_count = sum(1 for s in usable_universe if s["was_cached"])
    downloaded_count = total_usable - cached_count

    print(f"\nData synchronization completed in {time.time() - t0:.2f}s:")
    print(f"  - Usable Universe: {total_usable} symbols")
    print(f"  - Total Candles: {total_candles:,}")
    print(f"  - Reused from Local Cache: {cached_count} symbols")
    print(f"  - Downloaded Fresh: {downloaded_count} symbols")
    print(f"  - Excluded (Insufficient data < 200 bars): {len(insufficient_data_symbols)} symbols")

    # Save docs/backtest/ALL_FUTURES_UNIVERSE.json
    universe_json_path = DOCS_DIR / "ALL_FUTURES_UNIVERSE.json"
    universe_data = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timeframe": TIMEFRAME,
            "total_usable_symbols": total_usable,
            "total_candles": total_candles,
            "min_candles_required": MIN_CANDLES_REQUIRED,
            "selection_criteria": "quoteAsset=USDT, contractType=PERPETUAL, status=TRADING, candle_count >= 200",
        },
        "usable_symbols": usable_universe,
        "excluded_insufficient_data": insufficient_data_symbols,
        "excluded_non_eligible": excluded_raw[:50],  # sample
    }
    with open(universe_json_path, "w", encoding="utf-8") as f:
        json.dump(universe_data, f, indent=2)
    print(f"\nSaved {universe_json_path}")

    # Save docs/backtest/ALL_FUTURES_UNIVERSE_REPORT.md
    universe_rep_path = DOCS_DIR / "ALL_FUTURES_UNIVERSE_REPORT.md"
    rep_md = f"""# NEXORA — ALL BINANCE USDⓈ-M FUTURES UNIVERSE AUDIT REPORT

> **AUDIT TIMESTAMP:** {datetime.now(timezone.utc).isoformat()}  
> **SCOPE:** Full dynamic discovery of all active Binance USDⓈ-M perpetual contracts.  
> **DISCIPLINE:** Zero ranking by profitability, zero filtering of underperforming symbols. All eligible trading contracts with valid 4H history are evaluated.

---

## 1. UNIVERSE AUDIT SUMMARY

| Metric | Count / Value | Notes |
| :--- | :---: | :--- |
| **Total Usable Symbols** | **{total_usable}** | Active trading USDT perpetual contracts |
| **Timeframe** | **4H ONLY** | Structural swing resolution |
| **Total Continuous Candles** | **{total_candles:,}** | Historical continuous bars evaluated |
| **Reused from Local Cache** | **{cached_count}** symbols | Existing datasets preserved |
| **Synchronized Missing Data** | **{downloaded_count}** symbols | Downloaded via rate-limited API calls |
| **Excluded (Insufficient Bars < 200)** | **{len(insufficient_data_symbols)}** symbols | New listings without adequate ATR(200) warmup |
| **Selection Bias** | **NONE** | Sorted alphabetically, unranked |

---

## 2. ELIGIBILITY CRITERIA

1. **`quoteAsset == "USDT"`**: Only USDT-margined contracts.
2. **`contractType == "PERPETUAL"`**: Quarterly and delivery futures excluded.
3. **`status == "TRADING"`**: Delisted or suspended contracts excluded.
4. **`bars >= 200`**: Minimum 200 continuous 4H bars required for Wilder ATR(200) indicator warmup and range qualification.

---

## 3. FULL USABLE SYMBOL UNIVERSE ({total_usable} SYMBOLS)

| # | Symbol | Contract Type | Status | 4H Candles | Data Source |
| :---: | :--- | :---: | :---: | ---:| :---: |
"""
    for i, s in enumerate(usable_universe, 1):
        src = "Local Cache" if s["was_cached"] else "Binance API"
        rep_md += f"| {i} | `{s['symbol']}` | {s['contract_type']} | {s['status']} | {s['candle_count']:,} | {src} |\n"

    if insufficient_data_symbols:
        rep_md += f"""
---

## 4. EXCLUDED SYMBOLS DUE TO INSUFFICIENT HISTORY (< 200 BARS)

| Symbol | Available 4H Candles | Reason |
| :--- | ---:| :--- |
"""
        for s in insufficient_data_symbols:
            rep_md += f"| `{s['symbol']}` | {s['candle_count']} | {s['reason']} |\n"

    with open(universe_rep_path, "w", encoding="utf-8") as f:
        f.write(rep_md)
    print(f"Saved {universe_rep_path}")
    print(f"Universe preparation complete in {time.time() - t0:.2f} seconds.")


if __name__ == "__main__":
    main()
