"""Telegram message formatting templates."""

from core.models.signal import TradingSignal
from core.enums import SignalDirection


def format_signal_message(signal: TradingSignal) -> str:
    """Format trading signal according to the strict specification in Section 33."""
    if signal.direction in (SignalDirection.LONG, SignalDirection.LONG_DEVIATION):
        header = "🟢 RANGE BREAKOUT UP"
    else:
        header = "🔴 RANGE BREAKDOWN"

    text = f"""━━━━━━━━━━━━━━━━━━
<b>NEXORA</b>
<b>BINANCE FUTURES</b>
━━━━━━━━━━━━━━━━━━

{header}

<b>Symbol:</b> {signal.symbol}
<b>Timeframe:</b> {signal.timeframe}

<b>Range:</b>
Upper: {signal.range_upper:,.4f}
Lower: {signal.range_lower:,.4f}
Height: {signal.range_height_pct:.2f}%

Held: {signal.held_bars} bars

<b>Breakout:</b>
{signal.entry_price:,.4f}
Buffer: {signal.buffer_atr:.2f} ATR

<b>Entry:</b>
{signal.entry_price:,.4f}

<b>Stop:</b>
{signal.stop_loss:,.4f}

<b>Risk:</b>
{signal.risk_percent:.2f}%

<b>TP1:</b>
{signal.tp1:,.4f}

<b>TP2:</b>
{signal.tp2:,.4f}

<b>TP3:</b>
{signal.tp3:,.4f}

<b>Mode:</b>
{signal.trading_mode.value.upper()}

<b>Signal:</b>
<code>{signal.signal_id}</code>

━━━━━━━━━━━━━━━━━━"""
    return text


def format_status_message(
    mode: str,
    balance: float,
    equity: float,
    open_positions: int,
    daily_pnl: float,
    is_halted: bool
) -> str:
    return f"""━━━━━━━━━━━━━━━━━━
<b>NEXORA SYSTEM STATUS</b>
━━━━━━━━━━━━━━━━━━

<b>Mode:</b> {mode.upper()}
<b>Balance:</b> ${balance:,.2f}
<b>Equity:</b> ${equity:,.2f}
<b>Open Positions:</b> {open_positions}
<b>Daily PnL:</b> ${daily_pnl:+,.2f}
<b>Circuit Breaker:</b> {"🚨 TRIPPED" if is_halted else "✅ NORMAL"}

━━━━━━━━━━━━━━━━━━"""


def format_paper_signal_message(sig: dict) -> str:
    """Professional Telegram alert for candidate A2+D paper signals."""
    direction = sig.get("direction", "LONG").upper()
    ema_cond = (sig.get("ema50", 0) > sig.get("ema200", 0)) if is_long else (sig.get("ema50", 0) < sig.get("ema200", 0))
    ema_check = "✓" if ema_cond else "✗"
    price_cond = (sig.get("entry_price", 0) > sig.get("ema200", 0)) if is_long else (sig.get("entry_price", 0) < sig.get("ema200", 0))
    price_check = "✓" if price_cond else "✗"
    atr_check = "✓" if sig.get("atr", 0) > sig.get("atr_sma20", 0) else "✗"

    return f"""━━━━━━━━━━━━━━━━━━
<b>NEXORA PAPER SIGNAL</b>
━━━━━━━━━━━━━━━━━━

<b>{sig.get('symbol')}</b>
<b>{sig.get('timeframe')}</b>

<b>{direction} BREAKOUT</b>

<b>Range:</b>
Upper: {sig.get('range_top', 0):,.4f}
Lower: {sig.get('range_bottom', 0):,.4f}

<b>Confirmation:</b>
EMA50 {'&gt;' if is_long else '&lt;'} EMA200 {ema_check}
Price {'&gt;' if is_long else '&lt;'} EMA200 {price_check}
ATR Expansion {atr_check}

<b>Entry:</b>
{sig.get('entry_price', 0):,.4f}

<b>SL:</b>
{sig.get('stop_loss', 0):,.4f}

<b>Risk:</b>
{sig.get('risk_percent', 1.0):.2f}%

<b>Status:</b>
PAPER ONLY
━━━━━━━━━━━━━━━━━━"""


def format_paper_fill_message(fill: dict) -> str:
    """Format fill alert for simulated paper execution."""
    return f"""━━━━━━━━━━━━━━━━━━
<b>NEXORA PAPER ENTRY FILLED</b>
━━━━━━━━━━━━━━━━━━

<b>Symbol:</b> {fill.get('symbol')}
<b>Side:</b> {fill.get('side')}
<b>Order Type:</b> {fill.get('order_type', 'MARKET')}
<b>Simulated Fill:</b> {fill.get('avg_fill_price', 0):,.4f}
<b>Expected Entry:</b> {fill.get('expected_price', 0):,.4f}
<b>Slippage:</b> {fill.get('slippage_bps', 2.0):.1f} bps
<b>Fee:</b> ${fill.get('fee', 0.0):.4f} USDT
<b>Latency:</b> {fill.get('latency_ms', 25.0):.1f} ms
<b>Status:</b> PAPER ONLY
━━━━━━━━━━━━━━━━━━"""


def format_paper_close_message(trade: dict) -> str:
    """Format position closed alert for paper execution."""
    pnl = trade.get('net_pnl', 0.0)
    emoji = "🟢" if pnl >= 0 else "🔴"
    return f"""━━━━━━━━━━━━━━━━━━
<b>NEXORA PAPER POSITION CLOSED</b>
━━━━━━━━━━━━━━━━━━

<b>Symbol:</b> {trade.get('symbol')}
<b>Side:</b> {trade.get('side')}
<b>Exit Price:</b> {trade.get('exit_price', 0):,.4f}
<b>Exit Reason:</b> {trade.get('exit_reason')}
<b>Net PnL:</b> {emoji} ${pnl:+,.2f} USDT ({trade.get('r_multiple', 0.0):+.2f}R)
<b>Status:</b> PAPER ONLY
━━━━━━━━━━━━━━━━━━"""

