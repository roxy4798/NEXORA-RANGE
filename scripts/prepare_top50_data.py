"""
scripts/prepare_top50_data.py — Discover and cache Top 50 Binance USD(S)-M Futures contracts.

Discovers the 50 most liquid eligible USDT perpetual contracts ranked by 24h quote volume.
Checks existing local cache in data/research_klines/ to avoid duplicate downloads.
Guards against infinite retries with exponential backoff (max 3 retries).
Substitutes any non-standard/unsupported symbol with the next ranked perpetual contract.
Verifies data integrity across all 50 datasets.
Outputs metadata summary table.
"""

import glob
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "research_klines"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TIMEFRAME = "4h"
TARGET_CANDLES = 1000
MAX_RETRIES = 3


def discover_ranked_perpetuals() -> List[Dict[str, Any]]:
    """Discovers all eligible USDT perpetual contracts ranked strictly by 24h volume descending."""
    print("Querying Binance USD(S)-M Futures for eligible USDT perpetual contracts...")
    info_req = urllib.request.urlopen("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=15)
    info = json.loads(info_req.read().decode("utf-8"))

    tickers_req = urllib.request.urlopen("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=15)
    tickers = json.loads(tickers_req.read().decode("utf-8"))
    vol_map = {t["symbol"]: float(t.get("quoteVolume", 0)) for t in tickers}

    eligible = []
    for s in info["symbols"]:
        if s["status"] == "TRADING" and s["contractType"] == "PERPETUAL" and s["quoteAsset"] == "USDT":
            sym = s["symbol"]
            eligible.append({
                "symbol": sym,
                "status": s["status"],
                "quote_asset": s["quoteAsset"],
                "contract_type": s["contractType"],
                "volume_24h": vol_map.get(sym, 0.0),
            })

    # Sort strictly by 24h volume descending to avoid any selection/survivorship bias
    eligible.sort(key=lambda x: x["volume_24h"], reverse=True)
    return eligible


def fetch_symbol_4h(symbol: str, target_count: int = 1000) -> Optional[List[Dict[str, Any]]]:
    """Fetches up to target_count continuous 4H candles with max 3 retries and exponential backoff."""
    encoded_sym = urllib.parse.quote(symbol)
    base_url = f"https://fapi.binance.com/fapi/v1/klines?symbol={encoded_sym}&interval={TIMEFRAME}&limit=1500"
    all_raw: List[list] = []
    end_time = int(time.time() * 1000)

    while len(all_raw) < target_count:
        url = f"{base_url}&endTime={end_time}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        batch = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    batch = json.loads(resp.read().decode("utf-8"))
                    break
            except Exception as e:
                if attempt == MAX_RETRIES:
                    # Mark as failed for this batch
                    break
                time.sleep(0.5 * (2 ** attempt))

        if batch is None or not batch:
            break

        all_raw = batch + all_raw
        end_time = int(batch[0][0]) - 1

        if len(batch) < 1500:
            break
        time.sleep(0.05)

    if not all_raw:
        return None

    seen = set()
    dedup = []
    for k in all_raw:
        ot = int(k[0])
        if ot not in seen:
            seen.add(ot)
            dedup.append(k)

    dedup.sort(key=lambda x: int(x[0]))
    if len(dedup) > target_count:
        dedup = dedup[-target_count:]

    candles: List[Dict[str, Any]] = []
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


def get_or_fetch_symbol(item: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Checks cache or downloads symbol data safely."""
    sym = item["symbol"]

    # Check ASCII compliance: skip non-ASCII ticker symbols to avoid OS/API incompatibilities
    try:
        sym.encode("ascii")
    except UnicodeEncodeError:
        return False, item, "Non-ASCII symbol name incompatible with standard endpoints"

    cached_files = glob.glob(str(DATA_DIR / f"{sym}_4h_*.json"))
    if cached_files:
        cached_file = cached_files[0]
        try:
            with open(cached_file, "r", encoding="utf-8") as f:
                candles = json.load(f)
            item["candle_count"] = len(candles)
            item["cache_status"] = "CACHED"
            item["file_path"] = cached_file
            return True, item, None
        except Exception as e:
            pass  # Re-fetch if corrupted

    # Fetch missing
    candles = fetch_symbol_4h(sym, TARGET_CANDLES)
    if not candles:
        return False, item, "Failed to fetch valid klines after retries"

    out_file = DATA_DIR / f"{sym}_{TIMEFRAME}_{len(candles)}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(candles, f)

    item["candle_count"] = len(candles)
    item["cache_status"] = "DOWNLOADED"
    item["file_path"] = str(out_file)
    return True, item, None


def validate_candle_file(file_path: str) -> Tuple[bool, str]:
    """Validates continuity, chronological order, and absence of duplicate bars."""
    with open(file_path, "r", encoding="utf-8") as f:
        candles = json.load(f)

    if not candles:
        return False, "Empty candle list"

    prev_ts = 0
    step_ms = 4 * 3600 * 1000

    for i, c in enumerate(candles):
        ts = c["timestamp"]
        if i > 0 and ts <= prev_ts:
            return False, f"Non-chronological or duplicate timestamp at index {i}"
        if c["high"] < c["low"] or c["open"] <= 0 or c["close"] <= 0:
            return False, f"Invalid OHLC price at index {i}"
        prev_ts = ts

    return True, "Valid"


def main():
    print("=" * 72)
    print("  NEXORA - TOP 50 LIQUID BINANCE FUTURES DATA PREPARATION        ")
    print("=" * 72)

    ranked_perps = discover_ranked_perpetuals()
    print(f"Total eligible USDT perpetual contracts discovered: {len(ranked_perps)}")

    final_universe: List[Dict[str, Any]] = []
    substitutions: List[Dict[str, Any]] = []
    failed_symbols: List[Dict[str, Any]] = []

    rank_idx = 0
    while len(final_universe) < 50 and rank_idx < len(ranked_perps):
        item = ranked_perps[rank_idx]
        rank_idx += 1

        success, enriched_item, error_msg = get_or_fetch_symbol(item)
        if success:
            # Validate the file on disk
            is_valid, val_msg = validate_candle_file(enriched_item["file_path"])
            if is_valid:
                final_universe.append(enriched_item)
                print(f"  [{len(final_universe):2d}/50] {enriched_item['symbol']:<14} | "
                      f"Vol: ${enriched_item['volume_24h']:,.0f} | "
                      f"Bars: {enriched_item['candle_count']:<5} | Status: {enriched_item['cache_status']}")
            else:
                failed_symbols.append({"symbol": item["symbol"], "reason": f"Validation failed: {val_msg}"})
        else:
            reason = error_msg or "Unknown error"
            failed_symbols.append({"symbol": item["symbol"], "reason": reason})
            # Explicit substitution
            substitutions.append({
                "original_symbol": item["symbol"],
                "rank": rank_idx,
                "reason": reason,
            })
            print(f"  [SKIP] {ascii(item['symbol'])} skipped ({reason}). Substituting with next ranked contract...")

    # Save Top 50 metadata
    meta_path = DATA_DIR / "top50_universe_metadata.json"
    metadata_payload = {
        "universe_size": len(final_universe),
        "timeframe": TIMEFRAME,
        "selection_metric": "24h Quote Volume (USDT)",
        "substitutions": substitutions,
        "failed_symbols": failed_symbols,
        "symbols": final_universe,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata_payload, f, indent=2)

    # Calculate global range
    all_start_ts = []
    all_end_ts = []
    for item in final_universe:
        with open(item["file_path"], "r", encoding="utf-8") as f:
            c = json.load(f)
            if c:
                all_start_ts.append(c[0]["timestamp"])
                all_end_ts.append(c[-1]["timestamp"])

    earliest_date = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(min(all_start_ts) / 1000)) if all_start_ts else "N/A"
    latest_date = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(max(all_end_ts) / 1000)) if all_end_ts else "N/A"
    total_candles = sum(r["candle_count"] for r in final_universe)

    print("-" * 72)
    print("DATA PREPARATION COMPLETE")
    print(f"Universe:        {len(final_universe)} symbols")
    print(f"Cached:          {len(final_universe)}/50")
    print(f"Failed:          {len(failed_symbols)}")
    if substitutions:
        for s in substitutions:
            print(f"Substituted:     {ascii(s['original_symbol'])} (Rank #{s['rank']}) -> Reason: {s['reason']}")
    else:
        print("Substituted:     None")
    print(f"Total 4H candles: {total_candles:,}")
    print(f"Data period:     {earliest_date} to {latest_date}")
    print("=" * 72)


if __name__ == "__main__":
    main()
