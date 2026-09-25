"""Asynchronous Telegram Bot with interactive command routing and safety flows."""

import asyncio
from typing import Optional, Dict, Any
import httpx
from loguru import logger
from app.config import settings
from core.models.signal import TradingSignal
from telegram.messages import format_signal_message, format_status_message


class TelegramBotService:
    """Telegram alert and command listener service."""

    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.enabled = settings.TELEGRAM_ALERTS_ENABLED and bool(self.bot_token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._running: bool = False
        self._poll_task: Optional[asyncio.Task] = None
        self._pending_live_confirm: bool = False

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message via Telegram Bot API."""
        if not self.enabled:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                    }
                )
                return res.status_code == 200
        except Exception as exc:
            logger.error(f"Failed to dispatch Telegram message: {exc}")
            return False

    async def broadcast_signal(self, signal: TradingSignal):
        """Dispatch institutional trading signal."""
        msg = format_signal_message(signal)
        await self.send_message(msg)

    async def broadcast_alert(self, title: str, details: str):
        """Dispatch risk alert or bot lifecycle notice."""
        msg = f"<b>⚠️ NEXORA ALERT: {title}</b>\n\n{details}"
        await self.send_message(msg)

    async def start(self):
        """Start polling loop for incoming user commands."""
        if not self.enabled:
            logger.info("TelegramBotService: Disabled or credentials not configured.")
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_updates())
        logger.info("TelegramBotService: Started update polling loop.")

    async def _poll_updates(self):
        """Long polling for user commands."""
        offset = 0
        async with httpx.AsyncClient(timeout=35.0) as client:
            while self._running:
                try:
                    res = await client.get(
                        f"{self.base_url}/getUpdates",
                        params={"offset": offset, "timeout": 30}
                    )
                    if res.status_code == 200:
                        updates = res.json().get("result", [])
                        for u in updates:
                            offset = u["update_id"] + 1
                            msg = u.get("message", {})
                            text = msg.get("text", "").strip()
                            sender_chat = str(msg.get("chat", {}).get("id", ""))
                            
                            # Only respond to authorized chat_id
                            if sender_chat == str(self.chat_id):
                                await self._handle_command(text)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    if not self._running:
                        break
                    await asyncio.sleep(5.0)

    async def _handle_command(self, cmd: str):
        """Route user commands with confirmation checks."""
        cmd_lower = cmd.lower()

        if cmd_lower in ("/start", "/help"):
            help_text = (
                "<b>NEXORA RANGE SCANNER — COMMANDS:</b>\n\n"
                "/status — System health & active mode\n"
                "/balance — Current equity & margin\n"
                "/positions — Active open positions\n"
                "/signals — Recent detected signals\n"
                "/risk — Risk parameters & circuit status\n"
                "/pause — Halt trade execution\n"
                "/resume — Resume trading\n"
                "/paper — Switch to PAPER mode\n"
                "/live — Request switch to LIVE mode (Requires 2FA /live_confirm)\n"
            )
            await self.send_message(help_text)

        elif cmd_lower == "/status":
            from database.repository import Repository
            positions = await Repository.get_open_positions()
            msg = format_status_message(
                mode=settings.effective_trading_mode.value,
                balance=1000.0,
                equity=1000.0,
                open_positions=len(positions),
                daily_pnl=0.0,
                is_halted=not settings.GLOBAL_TRADING_ENABLED,
            )
            await self.send_message(msg)

        elif cmd_lower == "/live":
            self._pending_live_confirm = True
            msg = (
                "⚠️ <b>DANGER: LIVE TRADING ACTIVATION REQUESTED</b> ⚠️\n\n"
                "Real capital will be at risk. To confirm and engage LIVE execution, reply with:\n"
                "<code>/live_confirm</code>\n\n"
                "Or type <code>/cancel</code> to abort."
            )
            await self.send_message(msg)

        elif cmd_lower == "/live_confirm":
            if self._pending_live_confirm:
                self._pending_live_confirm = False
                await self.send_message("❌ LIVE mode requires setting LIVE_CONFIRMATION='CONFIRM_LIVE_TRADING' in .env.")
            else:
                await self.send_message("No pending LIVE activation request. Type /live first.")

        elif cmd_lower == "/cancel":
            self._pending_live_confirm = False
            await self.send_message("Action cancelled.")

    async def stop(self):
        """Stop polling loop."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
        logger.info("TelegramBotService stopped.")
