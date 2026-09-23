from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any


class HKMarketProvider:
    """Configurable read-only HK market-data adapter.

    HKEX real-time feeds are licensed/provider-delivered; this adapter never
    claims a feed is live unless the corresponding endpoint is configured.
    """
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.universe_url = os.getenv("SMART_TRADER_HK_UNIVERSE_URL", "").strip()
        self.quote_url = os.getenv("SMART_TRADER_HK_QUOTE_URL", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.universe_url and self.quote_url)

    def _get(self, base: str, params: dict[str, Any] | None = None) -> Any:
        if not base:
            raise RuntimeError("HK provider endpoint is not configured")
        url = base
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "SmartTrader/1.1"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def universe(self) -> Any:
        return self._get(self.universe_url)

    def quote(self, symbol: str) -> Any:
        return self._get(self.quote_url, {"symbol": symbol})

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "universe_endpoint": bool(self.universe_url),
            "quote_endpoint": bool(self.quote_url),
            "analysis_only": True,
            "provider_type": "licensed/provider HTTP adapter",
        }
