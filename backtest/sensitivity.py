"""Parameter sensitivity research and stability analysis module."""

from typing import List, Dict, Any
from core.models.candle import Candle
from strategy.parameters import RangeDetectorParameters
from backtest.engine import BacktestEngine


class ParameterSensitivityAnalyzer:
    """Evaluates parameter stability to avoid over-optimized peak curves."""

    @staticmethod
    def analyze_parameter(
        candles: List[Candle],
        param_name: str,
        values: List[Any],
        base_params: RangeDetectorParameters
    ) -> List[Dict[str, Any]]:
        """Run backtests varying a single parameter across a test range."""
        results = []

        for val in values:
            test_params = RangeDetectorParameters(
                scan_scaling=base_params.scan_scaling,
                base_scan_length=base_params.base_scan_length,
                boundary_basis=base_params.boundary_basis,
                boundary_percentile=base_params.boundary_percentile,
                atr_length=base_params.atr_length,
                compression_percentile=base_params.compression_percentile,
                calibration_lookback=base_params.calibration_lookback,
                min_rotation_rate=base_params.min_rotation_rate,
                min_boundary_touches=base_params.min_boundary_touches,
                touch_tolerance_atr=base_params.touch_tolerance_atr,
                max_drift=base_params.max_drift,
                min_containment=base_params.min_containment,
                minimum_range_bars=base_params.minimum_range_bars,
                absorb_overshoot=base_params.absorb_overshoot,
                overshoot_tolerance_atr=base_params.overshoot_tolerance_atr,
                breakout_buffer_atr=base_params.breakout_buffer_atr,
                merge_deviations=base_params.merge_deviations,
                deviation_window=base_params.deviation_window,
                cooldown_bars=base_params.cooldown_bars,
            )

            # Override target parameter
            setattr(test_params, param_name, val)

            engine = BacktestEngine(params=test_params)
            res = engine.run(candles)
            m = res.get("metrics", {})

            results.append({
                "parameter": param_name,
                "value": val,
                "total_trades": m.get("total_trades", 0),
                "win_rate": m.get("win_rate", 0.0),
                "profit_factor": m.get("profit_factor", 0.0),
                "net_pnl": m.get("net_pnl", 0.0),
                "max_drawdown_pct": m.get("max_drawdown_pct", 0.0),
                "expectancy_r": m.get("expectancy_r", 0.0),
            })

        return results
