from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


class BinanceUsdMMarketData:
    """Read-only Binance USDⓈ-M market-data adapter.

    The adapter is the single quote source for crypto in the application.
    It normalizes ticker, book ticker and mark-price/funding data into the
    application's market row without leaking Binance payloads upward.
    """

    def __init__(self, base_url: str = "https://data-api.binance.vision", timeout: float = 8.0, ttl: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.ttl = ttl
        self._cache: tuple[float, dict[str, dict[str, Any]]] = (0.0, {})

    async def quotes(self) -> dict[str, dict[str, Any]]:
        now = time.monotonic()
        if now - self._cache[0] < self.ttl and self._cache[1]:
            return self._cache[1]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            info_task = client.get(f"{self.base_url}/api/v3/exchangeInfo")
            ticker_task = client.get(f"{self.base_url}/api/v3/ticker/24hr")
            book_task = client.get(f"{self.base_url}/api/v3/ticker/bookTicker")
            info_resp, ticker_resp, book_resp = await asyncio.gather(
                info_task, ticker_task, book_task, return_exceptions=True
            )

        info_rows = self._json_object_symbols(info_resp)
        contracts = {
            str(x.get("symbol", "")).upper(): x
            for x in info_rows
            if isinstance(x, dict) and str(x.get("symbol", "")).strip()
        }
        ticker_rows = self._json_list(ticker_resp)
        book_rows = self._json_list(book_resp)
        books = {str(x.get("symbol", "")).upper(): x for x in book_rows if isinstance(x, dict)}

        out: dict[str, dict[str, Any]] = {}
        for raw in ticker_rows:
            if not isinstance(raw, dict):
                continue
            symbol = str(raw.get("symbol", "")).upper()
            contract = contracts.get(symbol, {})
            quote_asset = str(contract.get("quoteAsset", "")).upper()
            status = str(contract.get("status", "")).upper()
            # Classification comes from exchangeInfo, never from the 24h ticker.
            # Spot mode: quote USDT/USDC pairs only.
            if (not symbol or quote_asset not in {"USDT", "USDC"}
                    or (status and status != "TRADING")):
                continue
            try:
                row: dict[str, Any] = {
                    "price": float(raw["lastPrice"]),
                    "previous_close": float(raw["prevClosePrice"]),
                    "change_pct": float(raw["priceChangePercent"]),
                    "volume": float(raw["volume"]),
                    "quote_volume": float(raw.get("quoteVolume", 0.0)),
                    "trades": int(raw.get("count", 0)),
                    "source": "Binance Spot",
                    "market_data_type": "SPOT",
                    "quote_currency": quote_asset,
                    "base_asset": str(contract.get("baseAsset", "")),
                    "pair": symbol,
                    "contract_type": "SPOT",
                    "market_type": "SPOT",
                    "data_time": int(raw.get("closeTime") or raw.get("openTime") or time.time() * 1000),
                }
            except (KeyError, TypeError, ValueError):
                continue

            book = books.get(symbol)
            if book:
                row.update(
                    {
                        "bid": self._float(book.get("bidPrice")),
                        "bid_size": self._float(book.get("bidQty")),
                        "ask": self._float(book.get("askPrice")),
                        "ask_size": self._float(book.get("askQty")),
                        "book_data_time": book.get("time"),
                    }
                )
            row["quote_status"] = "live"
            out[symbol] = row

        if out:
            self._cache = (now, out)
        return out or self._cache[1]

    async def symbol_quote(self, symbol: str) -> dict[str, Any] | None:
        return (await self.quotes()).get(symbol.replace("/", "").replace("-", "").upper())

    @staticmethod
    def _float(value: Any) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _json_object_symbols(response: Any) -> list[Any]:
        if isinstance(response, Exception):
            return []
        try:
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []
        return data.get("symbols", []) if isinstance(data, dict) and isinstance(data.get("symbols"), list) else []

    @staticmethod
    def _json_list(response: Any) -> list[Any]:
        if isinstance(response, Exception):
            return []
        try:
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []
        return data if isinstance(data, list) else []
