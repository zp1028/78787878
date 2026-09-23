from __future__ import annotations
from typing import Any

from app.core.config import settings
from app.services.binance_terminal import BinanceUsdMTerminalService
from app.services.unified_analysis_report import UnifiedAnalysisReportService


class TerminalAnalysisService:
    """One read-only detail contract: market terminal facts + our analysis brain.

    The terminal side is provider truth (quotes/order-book/trades/mark/funding),
    while the analysis side is recalculated for the requested timeframe. No
    account, order, wallet, or execution state is included.
    """

    def __init__(self) -> None:
        self.terminal = BinanceUsdMTerminalService(settings.binance_rest_url)
        self.analysis = UnifiedAnalysisReportService()

    async def build(self, symbol: str, timeframe: str, depth_limit: int = 20, trade_limit: int = 20) -> dict[str, Any]:
        terminal, report = await _gather(
            self.terminal.snapshot(symbol, timeframe, depth_limit, trade_limit),
            self.analysis.build(symbol, "crypto", timeframe, 250),
        )
        return {
            "contract": "terminal-analysis-v1",
            "analysis_only": True,
            "read_only": True,
            "symbol": terminal.get("symbol", symbol.replace("/", "").upper()),
            "timeframe": timeframe,
            "terminal": terminal,
            "analysis": report,
            "integration": {
                "market_truth": "provider_snapshot",
                "analysis_truth": "recalculated_from_current_timeframe_klines",
                "closed_candle_required": True,
                "intrabar_note": "未收盘K线仅作为实时观察状态，结构突破/跌破需要对应周期收盘确认。",
            },
            "disclaimer": "仅用于市场研究与情景分析；不提供账户、钱包、模拟、下单或交易执行功能。",
        }


async def _gather(a, b):
    import asyncio
    return await asyncio.gather(a, b)
