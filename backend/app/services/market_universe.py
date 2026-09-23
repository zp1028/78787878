from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class UniverseItem:
    symbol: str
    name: str
    market: str
    asset_type: str
    venue: str
    currency: str | None = None
    metadata: dict[str, Any] | None = None


class MarketUniverseService:
    """Analysis-only market universe.

    The service separates symbol discovery from realtime subscriptions. This is
    important for large universes: the app can display/search every instrument,
    while realtime streams are opened only for selected/detail/watchlist items.
    """

    # No hard-coded commodity universe. A configured futures symbol master is required.


    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, list[UniverseItem]]] = {}
        self._ttl = 3600.0

    async def crypto(self) -> list[UniverseItem]:
        cached = self._cached("crypto")
        if cached is not None and cached:
            return cached
        from app.services.crypto_provider_gateway import CryptoProviderGateway
        gateway = CryptoProviderGateway()
        try:
            rows = await gateway.market_rows()
        except Exception:
            return []
        out = [UniverseItem(
            symbol=str(x["symbol"]),
            name=str(x.get("name") or x["symbol"]),
            market="crypto",
            asset_type="crypto",
            venue=str(x.get("venue") or x.get("provider") or "unknown"),
            currency=str(x.get("currency") or "USDT"),
            metadata={**(x.get("metadata") or {}), "provider": x.get("provider"), "quote_status": x.get("quote_status")},
        ) for x in rows]
        return self._put("crypto", out) if out else []

    async def us(self) -> list[UniverseItem]:
        cached = self._cached("us")
        if cached is not None:
            return cached
        # SEC's public company ticker master gives an exhaustive public US issuer
        # universe without inventing a hard-coded watchlist. Quote/realtime data
        # is resolved by the configured market-data provider later.
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": "SmartTrader/1.0 analysis app contact=local"}
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
        out = [UniverseItem(
            symbol=v["ticker"], name=v["title"], market="us", asset_type="stock",
            venue="sec", currency="USD", metadata={"cik": str(v["cik_str"]).zfill(10)},
        ) for v in data.values() if v.get("ticker")]
        return self._put("us", out)

    async def hk(self) -> list[UniverseItem]:
        # HK symbol masters vary by vendor. Do not pretend a tiny static list is
        # the full HKEX universe. A production provider can supply a CSV/JSON
        # symbol master through SMART_TRADER_HK_UNIVERSE_URL.
        import os
        url = os.getenv("SMART_TRADER_HK_UNIVERSE_URL", "").strip()
        if not url:
            return []
        cached = self._cached("hk")
        if cached is not None:
            return cached
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
        out = []
        for x in data if isinstance(data, list) else data.get("items", []):
            symbol = str(x.get("symbol", "")).strip()
            if not symbol:
                continue
            out.append(UniverseItem(
                symbol=symbol, name=x.get("name", symbol), market="hk", asset_type="stock",
                venue=x.get("venue", "hkex"), currency=x.get("currency", "HKD"),
                metadata=x,
            ))
        return self._put("hk", out)

    async def commodities(self) -> list[UniverseItem]:
        """Use only a configured futures symbol master.

        A missing provider intentionally returns an empty universe; a static
        commodity watchlist must never masquerade as full market discovery.
        """
        import os
        url = os.getenv("SMART_TRADER_COMMODITY_UNIVERSE_URL", "").strip()
        if not url:
            return []
        cached = self._cached("commodities")
        if cached is not None:
            return cached
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url); r.raise_for_status(); data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        out = []
        for x in items:
            symbol = str(x.get("symbol", "")).strip()
            if not symbol: continue
            out.append(UniverseItem(symbol, x.get("name", symbol), "commodities", "future",
                                     x.get("venue", "futures"), x.get("currency", "USD"),
                                     {**x, "universe_source": "configured_provider"}))
        return self._put("commodities", out)

    def _cached(self, key: str) -> list[UniverseItem] | None:
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self._ttl:
            return hit[1]
        return None

    def _put(self, key: str, value: list[UniverseItem]) -> list[UniverseItem]:
        self._cache[key] = (time.monotonic(), value)
        return value

    async def all(self) -> list[UniverseItem]:
        groups = await __import__("asyncio").gather(self.crypto(), self.us(), self.hk(), self.commodities())
        return [x for g in groups for x in g]
