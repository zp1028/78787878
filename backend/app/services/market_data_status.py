from __future__ import annotations
import os
from typing import Any


DEFAULT_CRYPTO_PROVIDER_ORDER = ("binance", "okx", "bybit")

def _crypto_provider_order() -> list[str]:
    raw = os.getenv("SMART_TRADER_CRYPTO_PROVIDER_ORDER", "").strip()
    requested = [x.strip().lower() for x in raw.split(",") if x.strip()] if raw else list(DEFAULT_CRYPTO_PROVIDER_ORDER)
    return [x for x in requested if x in DEFAULT_CRYPTO_PROVIDER_ORDER] or list(DEFAULT_CRYPTO_PROVIDER_ORDER)

class MarketDataStatusService:
    """Describes configured data capabilities without pretending unavailable feeds are live."""
    def snapshot(self) -> dict[str, Any]:
        hk = bool(os.getenv("SMART_TRADER_HK_UNIVERSE_URL"))
        hk_quote = bool(os.getenv("SMART_TRADER_HK_QUOTE_URL"))
        us_quote = os.getenv("SMART_TRADER_US_QUOTE_URL", "").strip()
        crypto_order = _crypto_provider_order()
        return {
            "analysis_only": True,
            "providers": {
                "crypto": {
                    "universe": "CryptoProviderGateway live instrument discovery",
                    "quotes": "CryptoProviderGateway paired live quotes",
                    "provider_order": crypto_order,
                    "configured": True,
                    "realtime": True,
                    "truth_note": "The active symbol owner is the first configured provider that supplies both the instrument and a live quote.",
                },
                "us": {
                    "universe": "SEC ticker/CIK discovery",
                    "quotes": "Configured synchronized provider when SMART_TRADER_US_QUOTE_URL is set; public chart data may support historical/intraday analysis but is not labelled realtime",
                    "configured": True,
                    "realtime": False,
                    "custom_quote_provider": bool(us_quote),
                },
                "hk": {
                    "universe": "HKEX/provider symbol master",
                    "quotes": "Configured provider only",
                    "configured": hk and hk_quote,
                    "realtime": hk_quote,
                    "missing": [x for x, ok in (("universe", hk), ("quote", hk_quote)) if not ok],
                },
                "commodities": {
                    "universe": "Configured futures symbol master only",
                    "quotes": "Provider required for synchronized futures quotes",
                    "configured": bool(os.getenv("SMART_TRADER_COMMODITY_UNIVERSE_URL")) and bool(os.getenv("SMART_TRADER_COMMODITY_QUOTE_URL")),
                    "realtime": bool(os.getenv("SMART_TRADER_COMMODITY_QUOTE_URL")),
                },
            },
            "truth_rule": "A market is not labelled fully covered unless symbol discovery and the required quote feed are both configured.",
        }
