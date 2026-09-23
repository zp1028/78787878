from __future__ import annotations
import os
import time
from typing import Any

class MarketCapabilityService:
    """Truthful machine-readable capability matrix for every market family."""
    def __init__(self):
        self._generated_at = 0.0
        self._cache: dict[str, Any] | None = None

    def get(self, market: str) -> dict[str, Any]:
        data = self.snapshot()
        key = market.lower().strip()
        item = data.get("markets", {}).get(key)
        if item is None:
            return {"market": key, "status": "unsupported", "analysis_only": True}
        return {"market": key, **item, "analysis_only": True}

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        if self._cache and now - self._generated_at < 30:
            return self._cache
        hk_universe = bool(os.getenv("SMART_TRADER_HK_UNIVERSE_URL"))
        hk_quote = bool(os.getenv("SMART_TRADER_HK_QUOTE_URL"))
        us_quote = bool(os.getenv("SMART_TRADER_US_QUOTE_URL"))
        commodity_universe = bool(os.getenv("SMART_TRADER_COMMODITY_UNIVERSE_URL"))
        commodity_quote = bool(os.getenv("SMART_TRADER_COMMODITY_QUOTE_URL"))
        self._cache = {
            "generated_at": int(now * 1000),
            "analysis_only": True,
            "markets": {
                "crypto": {
                    "universe": "Binance USDⓈ-M preferred; OKX/Bybit public derivatives fallback",
                    "provider": "binance_usdm_public + okx_public + bybit_public",
                    "universe_discovery": True, "quote": True, "candles": True,
                    "realtime": True, "derivatives": True,
                    "funding": True, "open_interest": True,
                    "long_short_ratio": True, "taker_flow": True,
                    "liquidations": True, "basis": True,
                    "status": "available",
                    "quality": "public_provider", "market_standard": "USD-M", "freshness": "realtime_or_provider_defined",
                },
                "us": {
                    "universe": "SEC issuer/ticker master",
                    "provider": "sec_xbrl + configurable_quote",
                    "universe_discovery": True, "fundamentals": True,
                    "quote": us_quote, "candles": True, "realtime": us_quote,
                    "valuation_multiples": us_quote,
                    "status": "available" if us_quote else "partial",
                    "missing": [] if us_quote else ["synchronized_quote_provider"],
                    "quality": "synchronized" if us_quote else "fundamentals_only_without_realtime_quote",
                },
                "hk": {
                    "universe": "configured HKEX/vendor symbol master",
                    "provider": "configured_hk_provider",
                    "universe_discovery": hk_universe, "quote": hk_quote,
                    "candles": hk_quote, "realtime": hk_quote,
                    "orderbook": hk_quote, "trades": hk_quote, "announcements": hk_quote,
                    "status": "available" if hk_universe and hk_quote else "provider_required",
                    "missing": (["universe_provider"] if not hk_universe else []) + (["quote_provider"] if not hk_quote else []),
                    "quality": "configured_provider" if hk_universe and hk_quote else "provider_required",
                },
                "commodities": {
                    "universe": "configured futures master only; no static fallback",
                    "provider": "configurable_quote",
                    "universe_discovery": commodity_universe, "quote": commodity_quote,
                    "candles": True, "realtime": commodity_quote,
                    "curve": commodity_quote, "basis": commodity_quote,
                    "status": "available" if commodity_quote and commodity_universe else "provider_required",
                    "missing": ([] if commodity_universe else ["futures_universe_provider"]) + ([] if commodity_quote else ["synchronized_futures_quote_provider"]),
                    "quality": "synchronized" if commodity_quote and commodity_universe else "provider_required",
                },
            },
            "truth_rule": "A capability is true only when a provider is configured or a public source demonstrably supplies that data. Unavailable fields are never filled with zero/default values.",
            "execution": {"orders": False, "account_connection": False, "paper_trading": False},
        }
        self._generated_at = now
        return self._cache
