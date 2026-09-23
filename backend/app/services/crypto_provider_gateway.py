from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Awaitable, Callable

import httpx

from app.data.market_klines import fetch_binance_klines, fetch_gate_klines, fetch_okx_klines, fetch_bybit_klines
from app.services.binance_usdm_market_data import BinanceUsdMMarketData
from app.services.crypto_market_fallback import CryptoMarketFallbackService


class CryptoProviderGateway:
    """Unified read-only crypto market gateway.

    The application consumes this gateway instead of choosing an exchange at
    the call site. Providers are ordered by configuration and every market row
    keeps its own provider/source so a fallback can never be mislabeled as the
    primary exchange.
    """

    DEFAULT_ORDER = ("binance", "gate", "okx", "bybit")

    def __init__(self, timeout: float = 8.0, fallback_timeout: float = 3.0):
        self.timeout = timeout
        # Fallback venues (OKX/Bybit) get a short timeout so an unreachable
        # provider cannot stall the whole market snapshot behind a long connect.
        self._fallback = CryptoMarketFallbackService(timeout=fallback_timeout)
        self._binance = BinanceUsdMMarketData(timeout=timeout)
        self._market_cache: tuple[float, list[dict[str, Any]]] = (0.0, [])
        self._cache_ttl = 3.0

    @property
    def order(self) -> tuple[str, ...]:
        raw = os.getenv("SMART_TRADER_CRYPTO_PROVIDER_ORDER", "").strip()
        requested = tuple(x.strip().lower() for x in raw.split(",") if x.strip()) if raw else self.DEFAULT_ORDER
        valid = tuple(x for x in requested if x in self.DEFAULT_ORDER)
        return valid or self.DEFAULT_ORDER

    async def _binance_rows(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        base = self._binance.base_url
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{base}/api/v3/exchangeInfo")
            response.raise_for_status()
            payload = response.json()
        rows: list[dict[str, Any]] = []
        for item in payload.get("symbols", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).upper()
            if not symbol or item.get("status") != "TRADING":
                continue
            if str(item.get("quoteAsset", "")).upper() not in {"USDT", "USDC"}:
                continue
            rows.append({
                "symbol": symbol,
                "name": item.get("baseAsset", symbol) + "/" + str(item.get("quoteAsset", "USDT")).upper(),
                "market": "crypto",
                "asset_type": "crypto",
                "venue": "binance",
                "currency": str(item.get("quoteAsset", "USDT")).upper(),
                "metadata": {
                    "base": item.get("baseAsset"),
                    "contract_type": "SPOT",
                    "market_type": "SPOT",
                    "provider": "binance",
                },
            })
        quotes = await self._binance.quotes()
        if not rows and not quotes:
            raise RuntimeError("Binance market discovery unavailable")
        return rows, quotes

    async def _provider_rows(self, provider: str):
        if provider == "binance":
            return await self._binance_rows()
        if provider == "gate":
            return await self._fallback.gate()
        if provider == "okx":
            return await self._fallback.okx()
        if provider == "bybit":
            return await self._fallback.bybit()
        raise ValueError(f"unknown crypto provider: {provider}")

    async def market_rows(self) -> list[dict[str, Any]]:
        """Return a deduplicated live crypto universe with paired quotes.

        Providers are attempted in configured priority order. A symbol is owned
        by the first provider that supplies both a discovered instrument and a
        live quote. This prevents the old failure mode where an OKX universe was
        paired with unrelated Binance quote rows.
        """
        now = time.monotonic()
        if self._market_cache[1] and now - self._market_cache[0] < self._cache_ttl:
            return [dict(x) for x in self._market_cache[1]]
        providers = self.order
        results = await asyncio.gather(
            *(self._provider_rows(name) for name in providers),
            return_exceptions=True,
        )
        rows_by_symbol: dict[str, dict[str, Any]] = {}
        failures: list[str] = []
        for provider, result in zip(providers, results):
            if isinstance(result, Exception):
                failures.append(f"{provider}: {result}")
                continue
            universe, quotes = result
            for item in universe:
                symbol = str(item.get("symbol", "")).upper().replace("/", "")
                quote = quotes.get(symbol)
                if not quote:
                    continue
                row = dict(item)
                row.update(quote)
                row["provider"] = provider
                row["venue"] = provider
                row["quote_status"] = "live"
                row.setdefault("metadata", {})
                rows_by_symbol.setdefault(symbol, row)
        if not rows_by_symbol:
            detail = "; ".join(failures) if failures else "no provider returned live rows"
            raise RuntimeError(f"crypto market providers unavailable: {detail}")
        result = list(rows_by_symbol.values())
        self._market_cache = (now, result)
        return [dict(x) for x in result]

    async def fetch_klines(self, symbol: str, timeframe: str, limit: int = 300) -> tuple[list[dict[str, Any]], str]:
        """Fetch candles using the same provider order as the market gateway."""
        funcs: dict[str, Callable[..., Awaitable[list[dict[str, Any]]]]] = {
            "binance": fetch_binance_klines,
            "gate": fetch_gate_klines,
            "okx": fetch_okx_klines,
            "bybit": fetch_bybit_klines,
        }
        errors: list[str] = []
        for provider in self.order:
            try:
                bars = await funcs[provider](symbol, timeframe, limit)
                if bars:
                    return bars, provider
            except Exception as exc:
                errors.append(f"{provider}: {exc}")
        raise RuntimeError("crypto candle providers unavailable: " + "; ".join(errors))

    async def health(self) -> list[dict[str, Any]]:
        results = await asyncio.gather(
            *(self._provider_rows(name) for name in self.order),
            return_exceptions=True,
        )
        out = []
        for provider, result in zip(self.order, results):
            if isinstance(result, Exception):
                out.append({"provider": provider, "healthy": False, "error": str(result)})
            else:
                universe, quotes = result
                out.append({"provider": provider, "healthy": bool(universe and quotes), "universe": len(universe), "quotes": len(quotes)})
        return out
