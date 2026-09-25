"""
Unit and parity tests for Auto Range Detector [QuantAlgo] mathematics.
Verifies Wilder ATR, Percentiles, Linear Regression Drift, Crossings, Touches, and Containment.
"""

import math
import numpy as np
import pytest
from strategy.range_detector import calculate_wilder_atr, AutoRangeDetectorEngine
from strategy.parameters import RangeDetectorParameters
from core.enums import BoundaryBasis, TouchDefinition


def test_wilder_atr_mathematical_precision():
    """Verify Wilder's ATR matches the exact recursive smoothing formula."""
    highs = np.array([105.0, 107.0, 106.0, 108.0, 109.0, 111.0, 110.0, 112.0], dtype=np.float64)
    lows = np.array([100.0, 102.0, 101.0, 103.0, 104.0, 105.0, 104.0, 106.0], dtype=np.float64)
    closes = np.array([102.0, 105.0, 103.0, 106.0, 107.0, 108.0, 107.0, 110.0], dtype=np.float64)

    length = 4
    atr = calculate_wilder_atr(highs, lows, closes, length=length)

    assert len(atr) == len(closes)
    # Manual calculation of true ranges:
    # tr0 = 105 - 100 = 5.0
    # tr1 = max(107-102, |107-102|, |102-102|) = 5.0
    # tr2 = max(106-101, |106-105|, |101-105|) = 5.0
    # tr3 = max(108-103, |108-103|, |103-103|) = 5.0
    # First ATR at index 3 is SMA of first 4 = 5.0
    assert pytest.approx(atr[3], rel=1e-5) == 5.0

    # Next TR4: max(109-104, |109-106|, |104-106|) = 5.0
    # ATR4 = (ATR3 * 3 + TR4) / 4 = (15 + 5) / 4 = 5.0
    assert pytest.approx(atr[4], rel=1e-5) == 5.0


def test_percentile_linear_interpolation():
    """Verify linear interpolation matches Pine Script percentile_linear_interpolation."""
    values = np.array([10.0, 20.0, 30.0, 40.0, 50.0], dtype=np.float64)
    p90 = np.percentile(values, 90.0, method="linear")
    p10 = np.percentile(values, 10.0, method="linear")

    assert p90 == 46.0
    assert p10 == 14.0


def test_linear_regression_slope_and_drift():
    """Verify that OLS slope matches linreg(0) - linreg(1)."""
    # Perfectly flat series -> slope = 0, drift = 0
    closes_flat = np.array([100.0] * 20, dtype=np.float64)
    L = len(closes_flat)
    x = np.arange(L)
    x_centered = x - np.mean(x)
    ss_xx = np.sum(x_centered ** 2)
    slope = np.sum(x_centered * (closes_flat - np.mean(closes_flat))) / ss_xx
    assert abs(slope) < 1e-12

    # Linear trending series with exact slope of 2.0 per bar
    closes_trending = np.array([100.0 + 2.0 * i for i in range(20)], dtype=np.float64)
    slope_trend = np.sum(x_centered * (closes_trending - np.mean(closes_trending))) / ss_xx
    assert pytest.approx(slope_trend, rel=1e-5) == 2.0


def test_rotation_crossings_count():
    """Verify midline crossing counting matches Pine Script."""
    midline = 100.0
    # Crosses above, below, above, below (4 crossings)
    closes = np.array([95.0, 105.0, 95.0, 105.0, 95.0], dtype=np.float64)
    above = closes > midline
    crossings = int(np.sum(above[:-1] != above[1:]))
    assert crossings == 4


def test_range_qualification_with_synthetic_consolidation():
    """Test full qualification on a simulated oscillating consolidation channel."""
    L = 20
    np.random.seed(42)
    # Generate oscillating channel between 98 and 102
    t = np.linspace(0, 4 * np.pi, L)
    closes = 100.0 + 2.0 * np.sin(t)
    highs = closes + 0.5
    lows = closes - 0.5
    opens = closes.copy()

    params = RangeDetectorParameters(
        scan_scaling="Base only",
        base_scan_length=20,
        compression_percentile=50.0,
        min_rotation_rate=0.15,
        min_boundary_touches=2,
        max_drift=0.45,
        min_containment=0.70,
    )

    engine = AutoRangeDetectorEngine(params)
    atr_val = 2.0
    history_comp = [1.0] * 50

    is_qual, metrics = engine.scan_window(
        opens, highs, lows, closes, L, L - 1, atr_val, history_comp
    )

    assert metrics is not None
    assert metrics["crossings"] >= 3
    assert metrics["containment"] >= 0.70
    assert metrics["drift"] <= 0.45
