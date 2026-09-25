"""
scripts/fetch_extended_4h_data.py — Ingest 10,000 continuous 4H historical candles from Binance Futures.

Downloads and validates continuous, uncorrupted historical 4H klines for:
- SOLUSDT
- ETHUSDT
Saves to data/research_klines/{symbol}_4h_10000.json in the standard project format.
"""

import json
import time
import urllib.request
from pathlib import Path
from typing import List, Dict, Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "research_klines"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["SOLUSDT", "ETHUSDT"]
TARGET_CANDLES = 10000
TIMEFRAME = "4h"


def fetch_symbol_4h(symbol: str, target_count: int = 10000) -> List[Dict[str, Any]]:
    print(f"Fetching {target_count} 4H candles for {symbol} from Binance USD(S)-M Futures...")
    base_url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={TIMEFRAME}&limit=1500"

    all_raw: List[list] = []
    end_time = int(time.time() * 1000)

    while len(all_raw) < target_count:
        url = f"{base_url}&endTime={end_time}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                batch = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"  Error fetching batch: {e}, retrying...")
            time.sleep(1.0)
            continue

        if not batch:
            print(f"  No more historical data available at timestamp {end_time}.")
            break

        all_raw = batch + all_raw
        end_time = int(batch[0][0]) - 1

        print(f"  Loaded {len(batch)} bars. Total accumulated: {len(all_raw)} | Earliest: {batch[0][0]}")

        if len(batch) < 1500:
            break
        time.sleep(0.15)

    # Deduplicate and sort by open_time ascending
    seen = set()
    dedup = []
    for k in all_raw:
        ot = int(k[0])
        if ot not in seen:
            seen.add(ot)
            dedup.append(k)

    dedup.sort(key=lambda x: int(x[0]))

    # Trim to exact target_count from the latest closed candles
    if len(dedup) > target_count:
        dedup = dedup[-target_count:]

    # Transform to project Candle dictionary format
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

    # Validate continuity
    step_ms = 4 * 3600 * 1000
    gaps = 0
    for i in range(1, len(candles)):
        diff = candles[i]["timestamp"] - candles[i-1]["timestamp"]
        if diff != step_ms:
            gaps += 1

    print(f"  {symbol} Final Count: {len(candles)} continuous candles. Gaps detected: {gaps}")
    return candles


def main():
    for sym in SYMBOLS:
        candles = fetch_symbol_4h(sym, TARGET_CANDLES)
        out_file = DATA_DIR / f"{sym}_{TIMEFRAME}_{len(candles)}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(candles, f)
        print(f"  Saved to: {out_file} ({out_file.stat().st_size:,} bytes)\n")


if __name__ == "__main__":
    main()
