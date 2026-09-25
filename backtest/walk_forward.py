"""Walk-forward optimization and out-of-sample validation engine."""

from typing import List, Dict, Any, Optional
from core.models.candle import Candle
from strategy.parameters import RangeDetectorParameters
from backtest.engine import BacktestEngine


class WalkForwardValidator:
    """
    Partitions datasets into In-Sample (Train) and Out-Of-Sample (Test) periods.
    Prevents overfitting and confirms true out-of-sample expectancy.
    """

    @staticmethod
    def validate(
        candles: List[Candle],
        params: Optional[RangeDetectorParameters] = None,
        train_ratio: float = 0.70
    ) -> Dict[str, Any]:
        """Split dataset into train and test periods and evaluate separately."""
        n = len(candles)
        if n < 400:
            return {"error": "Insufficient history for walk-forward validation (min 400 bars required)"}

        split_idx = int(n * train_ratio)
        train_candles = candles[:split_idx]
        test_candles = candles[split_idx:]

        engine_train = BacktestEngine(params=params)
        engine_test = BacktestEngine(params=params)

        res_train = engine_train.run(train_candles)
        res_test = engine_test.run(test_candles)

        train_metrics = res_train.get("metrics", {})
        test_metrics = res_test.get("metrics", {})

        # Compute Overfit Degradation Ratio
        train_pf = train_metrics.get("profit_factor", 1.0)
        test_pf = test_metrics.get("profit_factor", 1.0)
        stability_ratio = (test_pf / max(train_pf, 1e-9)) if train_pf > 0 else 0.0

        return {
            "in_sample": {
                "bars": len(train_candles),
                "metrics": train_metrics,
            },
            "out_of_sample": {
                "bars": len(test_candles),
                "metrics": test_metrics,
            },
            "stability_ratio": round(stability_ratio, 2),
            "is_robust": bool(stability_ratio >= 0.70 and test_metrics.get("net_pnl", 0) > 0),
        }
