from __future__ import annotations
from typing import Any

from app.services.crypto_multi_exchange import CryptoMultiExchangeService
from app.services.crypto_derivatives import BinanceDerivativesService


class AnalysisEnrichmentService:
    """Read-only market evidence enrichment for the unified analysis contract."""
    def __init__(self):
        self.multi = CryptoMultiExchangeService()
        self.derivatives = BinanceDerivativesService()

    async def enrich(self, symbol: str, market: str, timeframe: str) -> dict[str, Any]:
        if market.lower() != "crypto":
            return {"market": market, "available": False, "reason": "no crypto derivatives enrichment for this market"}
        period = timeframe if timeframe in {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"} else "1h"
        multi, derivatives = await _gather_safe(
            self.multi.snapshot(symbol),
            self.derivatives.snapshot(symbol, period),
        )
        return {
            "market": "crypto",
            "available": True,
            "timeframe": timeframe,
            "multi_exchange": multi if isinstance(multi, dict) else {"available": False, "reason": str(multi)},
            "binance_derivatives": derivatives if isinstance(derivatives, dict) else {"available": False, "reason": str(derivatives)},
            "read_only": True,
            "analysis_only": True,
        }


async def _gather_safe(a, b):
    import asyncio
    async def safe(coro):
        try:
            return await coro
        except Exception as exc:
            return {"available": False, "reason": str(exc)}
    return await asyncio.gather(safe(a), safe(b))
