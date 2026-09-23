from __future__ import annotations

import os
from typing import Any

DEFAULT_CRYPTO_PROVIDER_ORDER = ("binance", "okx", "bybit")

def _crypto_provider_order() -> list[str]:
    raw = os.getenv("SMART_TRADER_CRYPTO_PROVIDER_ORDER", "").strip()
    requested = [x.strip().lower() for x in raw.split(",") if x.strip()] if raw else list(DEFAULT_CRYPTO_PROVIDER_ORDER)
    return [x for x in requested if x in DEFAULT_CRYPTO_PROVIDER_ORDER] or list(DEFAULT_CRYPTO_PROVIDER_ORDER)

from app.services.market_universe import MarketUniverseService


class MarketCoverageService:
    def __init__(self, universe: MarketUniverseService | None = None) -> None:
        self.universe = universe or MarketUniverseService()

    async def snapshot(self) -> dict[str, Any]:
        crypto, us, hk, commodities = await __import__("asyncio").gather(
            self.universe.crypto(), self.universe.us(), self.universe.hk(), self.universe.commodities()
        )
        return {
            "generated_at": __import__("time").time_ns() // 1_000_000,
            "analysis_only": True,
            "markets": {
                "crypto": {
                    "count": len(crypto),
                    "universe": "CryptoProviderGateway",
                    "provider_order": _crypto_provider_order(),
                    "realtime": True,
                },
                "us": {"count": len(us), "universe": "SEC issuer/ticker master", "realtime": False, "quote_note": "SEC ticker master is discovery metadata, not a quote feed."},
                "hk": {"count": len(hk), "universe": "HKEX/provider configured", "realtime": False, "configured": bool(os.getenv("SMART_TRADER_HK_UNIVERSE_URL"))},
                "commodities": {"count": len(commodities), "universe": "Configured futures symbol master", "realtime": False},
            },
            "coverage_rule": "Never label a market as fully covered unless its symbol master and quote provider are configured.",
        }
