"""
database/research_repository.py — Async repository for strategy research persistence.
Stores research runs, filter configurations, closed trade logs, advanced metrics, and walk-forward splits.
"""

from typing import List, Dict, Any, Optional
import time
from sqlalchemy import select, desc
from database.database import AsyncSessionFactory
from database.models import (
    ResearchRunModel, ResearchConfigModel, ResearchTradeModel,
    ResearchMetricModel, ResearchWalkForwardModel
)


class ResearchRepository:
    """Persistence manager for quantitative strategy research runs."""

    @staticmethod
    async def create_run(
        run_id: str,
        name: str,
        symbol: str,
        timeframe: str,
        bars_tested: int,
        description: Optional[str] = None
    ) -> ResearchRunModel:
        async with AsyncSessionFactory() as session:
            run_obj = ResearchRunModel(
                id=run_id,
                created_at=int(time.time() * 1000),
                name=name,
                description=description,
                symbol=symbol,
                timeframe=timeframe,
                bars_tested=bars_tested,
                status="COMPLETED",
            )
            session.add(run_obj)
            await session.commit()
            return run_obj

    @staticmethod
    async def save_config(run_id: str, filter_name: str, config_data: Dict[str, Any]) -> None:
        async with AsyncSessionFactory() as session:
            cfg = ResearchConfigModel(
                run_id=run_id,
                filter_name=filter_name,
                enable_trend_filter=config_data.get("enable_trend_filter", False),
                trend_filter_type=config_data.get("trend_mode"),
                enable_htf_filter=config_data.get("enable_htf_filter", False),
                htf_timeframe=config_data.get("htf_timeframe"),
                enable_volume_filter=config_data.get("enable_volume_filter", False),
                volume_multiplier=config_data.get("volume_mult_threshold", 1.0),
                enable_atr_filter=config_data.get("enable_atr_filter", False),
                atr_regime=config_data.get("atr_regime"),
                enable_breakout_strength_filter=config_data.get("enable_breakout_strength_filter", False),
                min_breakout_atr=config_data.get("min_breakout_atr", 0.0),
                enable_candle_filter=config_data.get("enable_candle_filter", False),
                min_body_ratio=config_data.get("min_body_ratio", 0.0),
                min_close_location=config_data.get("min_close_location", 0.0),
                enable_range_quality_filter=config_data.get("enable_range_quality_filter", False),
                min_range_bars=config_data.get("min_range_duration_bars", 10),
                min_compression_rank=config_data.get("min_compression_rank", 0.0),
                enable_retest_filter=config_data.get("enable_retest_filter", False),
                retest_buffer_atr=config_data.get("retest_buffer_atr", 0.0),
                enable_deviation_strategy=config_data.get("enable_deviation_strategy", False),
                raw_config_json=str(config_data),
            )
            session.add(cfg)
            await session.commit()

    @staticmethod
    async def save_metrics(run_id: str, symbol: str, timeframe: str, filter_name: str, metrics: Dict[str, Any]) -> None:
        async with AsyncSessionFactory() as session:
            metric_obj = ResearchMetricModel(
                run_id=run_id,
                symbol=symbol,
                timeframe=timeframe,
                filter_name=filter_name,
                trades=metrics.get("trades", 0),
                long_trades=metrics.get("long_trades", 0),
                short_trades=metrics.get("short_trades", 0),
                win_rate=metrics.get("win_rate", 0.0),
                long_win_rate=metrics.get("long_win_rate", 0.0),
                short_win_rate=metrics.get("short_win_rate", 0.0),
                profit_factor=metrics.get("profit_factor", 0.0),
                expectancy=metrics.get("expectancy", 0.0),
                average_r=metrics.get("average_r", 0.0),
                median_r=metrics.get("median_r", 0.0),
                net_pnl=metrics.get("net_pnl", 0.0),
                max_drawdown_pct=metrics.get("max_drawdown_pct", 0.0),
                sharpe=metrics.get("sharpe", 0.0),
                sortino=metrics.get("sortino", 0.0),
                calmar=metrics.get("calmar", 0.0),
                average_trade_duration=metrics.get("average_trade_duration", 0.0),
                max_consecutive_losses=metrics.get("max_consecutive_losses", 0),
                profit_concentration=metrics.get("profit_concentration", 0.0),
                symbol_concentration=metrics.get("symbol_concentration", 0.0),
                regime_trending_pf=metrics.get("regime_trending_pf", 0.0),
                regime_ranging_pf=metrics.get("regime_ranging_pf", 0.0),
                regime_high_vol_pf=metrics.get("regime_high_vol_pf", 0.0),
                regime_low_vol_pf=metrics.get("regime_low_vol_pf", 0.0),
            )
            session.add(metric_obj)
            await session.commit()

    @staticmethod
    async def save_trades(run_id: str, trades: List[Dict[str, Any]], filter_name: str) -> None:
        if not trades:
            return
        async with AsyncSessionFactory() as session:
            for t in trades:
                session.add(ResearchTradeModel(
                    run_id=run_id,
                    symbol=t["symbol"],
                    timeframe=t["timeframe"],
                    filter_name=filter_name,
                    side=t["side"],
                    entry_price=t["entry_price"],
                    exit_price=t["exit_price"],
                    quantity=t["quantity"],
                    gross_pnl=t["gross_pnl"],
                    net_pnl=t["net_pnl"],
                    commission=t["commission"],
                    r_multiple=t["r_multiple"],
                    exit_reason=t["exit_reason"],
                    regime=t.get("regime", "UNKNOWN"),
                    opened_at=t["opened_at"],
                    closed_at=t["closed_at"],
                    duration_bars=t.get("duration_bars", 1),
                ))
            await session.commit()

    @staticmethod
    async def save_walk_forward(
        run_id: str,
        filter_name: str,
        window_index: int,
        in_sample_pf: float,
        out_of_sample_pf: float,
        stability_ratio: float,
        start_time: int,
        split_time: int,
        end_time: int
    ) -> None:
        async with AsyncSessionFactory() as session:
            session.add(ResearchWalkForwardModel(
                run_id=run_id,
                filter_name=filter_name,
                window_index=window_index,
                in_sample_pf=in_sample_pf,
                out_of_sample_pf=out_of_sample_pf,
                stability_ratio=stability_ratio,
                start_time=start_time,
                split_time=split_time,
                end_time=end_time,
            ))
            await session.commit()

    @staticmethod
    async def get_all_metrics() -> List[Dict[str, Any]]:
        """Retrieve all research metric rows for reporting and dashboard."""
        async with AsyncSessionFactory() as session:
            stmt = select(ResearchMetricModel).order_by(desc(ResearchMetricModel.id))
            res = await session.execute(stmt)
            rows = res.scalars().all()
            return [
                {
                    "run_id": r.run_id,
                    "symbol": r.symbol,
                    "timeframe": r.timeframe,
                    "filter_name": r.filter_name,
                    "trades": r.trades,
                    "win_rate": r.win_rate,
                    "profit_factor": r.profit_factor,
                    "expectancy": r.expectancy,
                    "net_pnl": r.net_pnl,
                    "max_drawdown_pct": r.max_drawdown_pct,
                    "sharpe": r.sharpe,
                    "regime_trending_pf": r.regime_trending_pf,
                    "regime_ranging_pf": r.regime_ranging_pf,
                }
                for r in rows
            ]
