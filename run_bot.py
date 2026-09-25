"""NEXORA RANGE SCANNER — Application Entry Point."""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"==================================================")
    print(f"  NEXORA RANGE SCANNER — BINANCE FUTURES SYSTEM  ")
    print(f"  Mode: {settings.effective_trading_mode.value.upper()} (Default: PAPER)")
    print(f"  Global Trading Enabled: {settings.GLOBAL_TRADING_ENABLED}")
    print(f"  Dashboard: http://{settings.DASHBOARD_HOST}:{settings.DASHBOARD_PORT}")
    print(f"==================================================")

    uvicorn.run(
        "app.main:app",
        host=settings.DASHBOARD_HOST,
        port=settings.DASHBOARD_PORT,
        reload=False,
        log_level="info",
    )
