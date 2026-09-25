"""
Market Regime Classifier: Identifies structural market regimes for systematic strategy research.
Classifies historical bars into:
- TRENDING vs RANGING (via ADX & EMA trend structure)
- HIGH_VOLATILITY vs LOW_VOLATILITY (via ATR vs rolling ATR benchmark)
"""

from typing import Dict, Any, Tuple
import numpy as np


class MarketRegimeClassifier:
    """Classifies market conditions into objective volatility and trend regimes."""

    @staticmethod
    def calculate_ema(data: np.ndarray, span: int) -> np.ndarray:
        """Calculate Exponential Moving Average."""
        alpha = 2.0 / (span + 1.0)
        ema = np.zeros_like(data, dtype=np.float64)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1.0 - alpha) * ema[i - 1]
        return ema

    @staticmethod
    def calculate_adx(
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        length: int = 14
    ) -> np.ndarray:
        """Calculate standard Average Directional Index (ADX)."""
        n = len(closes)
        if n < length * 2:
            return np.zeros(n, dtype=np.float64)

        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )

        # Smooth TR, PlusDM, MinusDM with Wilder smoothing
        smoothed_tr = np.zeros(n - 1, dtype=np.float64)
        smoothed_pdm = np.zeros(n - 1, dtype=np.float64)
        smoothed_mdm = np.zeros(n - 1, dtype=np.float64)

        smoothed_tr[length - 1] = np.sum(tr[:length])
        smoothed_pdm[length - 1] = np.sum(plus_dm[:length])
        smoothed_mdm[length - 1] = np.sum(minus_dm[:length])

        for i in range(length, n - 1):
            smoothed_tr[i] = smoothed_tr[i - 1] - (smoothed_tr[i - 1] / length) + tr[i]
            smoothed_pdm[i] = smoothed_pdm[i - 1] - (smoothed_pdm[i - 1] / length) + plus_dm[i]
            smoothed_mdm[i] = smoothed_mdm[i - 1] - (smoothed_mdm[i - 1] / length) + minus_dm[i]

        pdi = np.zeros(n - 1, dtype=np.float64)
        mdi = np.zeros(n - 1, dtype=np.float64)
        dx = np.zeros(n - 1, dtype=np.float64)

        valid = smoothed_tr > 0
        pdi[valid] = 100.0 * (smoothed_pdm[valid] / smoothed_tr[valid])
        mdi[valid] = 100.0 * (smoothed_mdm[valid] / smoothed_tr[valid])

        di_sum = pdi + mdi
        valid_dx = di_sum > 0
        dx[valid_dx] = 100.0 * np.abs(pdi[valid_dx] - mdi[valid_dx]) / di_sum[valid_dx]

        adx = np.zeros(n, dtype=np.float64)
        # Smooth DX to get ADX
        start_adx = length * 2 - 2
        if start_adx < n - 1:
            adx[start_adx + 1] = np.mean(dx[length - 1:start_adx + 1])
            for i in range(start_adx + 1, n - 1):
                adx[i + 1] = (adx[i] * (length - 1) + dx[i]) / length

        return adx

    @classmethod
    def classify_bar(
        cls,
        bar_idx: int,
        atrs: np.ndarray,
        adx: np.ndarray,
        vol_benchmark_len: int = 50,
        trend_adx_threshold: float = 25.0
    ) -> Tuple[str, str, str]:
        """
        Classifies bar into:
        - trend_regime: 'TRENDING' or 'RANGING'
        - vol_regime: 'HIGH_VOLATILITY' or 'LOW_VOLATILITY'
        - combined_regime: e.g. 'TRENDING_HIGH_VOL'
        """
        if bar_idx < vol_benchmark_len:
            atr_ma = atrs[bar_idx]
        else:
            atr_ma = np.mean(atrs[bar_idx - vol_benchmark_len:bar_idx])

        current_atr = atrs[bar_idx]
        vol_regime = "HIGH_VOLATILITY" if current_atr > atr_ma else "LOW_VOLATILITY"

        current_adx = adx[bar_idx]
        trend_regime = "TRENDING" if current_adx >= trend_adx_threshold else "RANGING"

        combined = f"{trend_regime}_{vol_regime}"
        return trend_regime, vol_regime, combined
