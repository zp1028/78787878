from __future__ import annotations

import asyncio
from typing import Any
import httpx


class CryptoMarketFallbackService:
    """Read-only public crypto market discovery/quotes fallback.

    Binance remains the preferred USD-M source. When its public API is blocked
    (for example HTTP 451), OKX and Bybit public market-data APIs provide a
    truthful live universe instead of leaving the market page empty.
    """

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    @staticmethod
    def _norm(symbol: str) -> str:
        return symbol.replace("/", "").replace("-", "").replace("_", "").upper()

    @staticmethod
    def _okx_inst(symbol: str) -> str:
        s = CryptoMarketFallbackService._norm(symbol)
        if s.endswith("USDT"):
            return s[:-4] + "-USDT-SWAP"
        return s + "-USDT-SWAP"

    async def _get(self, client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None):
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def okx(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        base = "https://www.okx.com"
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            try:
                instruments, tickers = await asyncio.gather(
                    self._get(c, base + "/api/v5/public/instruments", {"instType": "SWAP"}),
                    self._get(c, base + "/api/v5/market/tickers", {"instType": "SWAP"}),
                )
            except Exception:
                return [], {}
        inst_rows = instruments.get("data", []) if isinstance(instruments, dict) else []
        ticker_rows = tickers.get("data", []) if isinstance(tickers, dict) else []
        ticker_map = {str(x.get("instId", "")).upper(): x for x in ticker_rows if isinstance(x, dict)}
        universe: list[dict[str, Any]] = []
        quotes: dict[str, dict[str, Any]] = {}
        for x in inst_rows:
            if not isinstance(x, dict) or str(x.get("state", "")).lower() != "live":
                continue
            inst_id = str(x.get("instId", "")).upper()
            if not inst_id.endswith("-USDT-SWAP"):
                continue
            raw = inst_id.replace("-", "")
            ticker = ticker_map.get(inst_id, {})
            universe.append({
                "symbol": raw,
                "name": inst_id,
                "market": "crypto",
                "asset_type": "crypto",
                "venue": "okx",
                "currency": "USDT",
                "metadata": {"base": x.get("ctValCcy") or raw[:-8], "contract_type": "PERPETUAL", "market_type": "SWAP", "provider": "okx"},
            })
            if ticker.get("last"):
                quotes[raw] = {
                    "price": float(ticker["last"]),
                    "previous_close": float(ticker.get("sodUtc0") or ticker.get("open24h") or ticker["last"]),
                    "change_pct": self._pct(ticker.get("last"), ticker.get("open24h")),
                    "volume": self._float(ticker.get("vol24h")),
                    "quote_volume": self._float(ticker.get("volCcy24h")),
                    "source": "OKX SWAP",
                    "market_data_type": "SWAP",
                    "quote_currency": "USDT",
                    "base_asset": raw[:-4],
                    "pair": raw,
                    "contract_type": "PERPETUAL",
                    "market_type": "SWAP",
                    "data_time": self._int(ticker.get("ts")),
                    "quote_status": "live",
                    "provider": "okx",
                }
        return universe, quotes

    async def bybit(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        base = "https://api.bybit.com"
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            try:
                instruments, tickers = await asyncio.gather(
                    self._get(c, base + "/v5/market/instruments-info", {"category": "linear", "limit": "1000"}),
                    self._get(c, base + "/v5/market/tickers", {"category": "linear"}),
                )
            except Exception:
                return [], {}
        inst_rows = ((instruments.get("result") or {}).get("list") or []) if isinstance(instruments, dict) else []
        ticker_rows = ((tickers.get("result") or {}).get("list") or []) if isinstance(tickers, dict) else []
        ticker_map = {str(x.get("symbol", "")).upper(): x for x in ticker_rows if isinstance(x, dict)}
        universe: list[dict[str, Any]] = []
        quotes: dict[str, dict[str, Any]] = {}
        for x in inst_rows:
            if not isinstance(x, dict) or str(x.get("status", "")).upper() != "TRADING":
                continue
            raw = str(x.get("symbol", "")).upper()
            if not raw.endswith("USDT") or not raw:
                continue
            ticker = ticker_map.get(raw, {})
            universe.append({
                "symbol": raw,
                "name": raw,
                "market": "crypto",
                "asset_type": "crypto",
                "venue": "bybit",
                "currency": "USDT",
                "metadata": {"base": x.get("baseCoin") or raw[:-4], "contract_type": "PERPETUAL", "market_type": "linear", "provider": "bybit"},
            })
            if ticker.get("lastPrice"):
                quotes[raw] = {
                    "price": self._float(ticker.get("lastPrice")),
                    "previous_close": self._float(ticker.get("prevPrice24h")) or self._float(ticker.get("lastPrice")),
                    "change_pct": self._pct(ticker.get("lastPrice"), ticker.get("prevPrice24h")),
                    "volume": self._float(ticker.get("volume24h")),
                    "quote_volume": self._float(ticker.get("turnover24h")),
                    "source": "Bybit Linear",
                    "market_data_type": "linear",
                    "quote_currency": "USDT",
                    "base_asset": raw[:-4],
                    "pair": raw,
                    "contract_type": "PERPETUAL",
                    "market_type": "linear",
                    "data_time": None,
                    "quote_status": "live",
                    "provider": "bybit",
                }
        return universe, quotes

    async def gate(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        """Gate.io spot market (public, no auth). Reachable in restricted
        networks where OKX/Bybit are blocked, so it is a real second source."""
        base = "https://api.gateio.ws"
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            try:
                pairs, tickers = await asyncio.gather(
                    self._get(c, base + "/api/v4/spot/currency_pairs"),
                    self._get(c, base + "/api/v4/spot/tickers"),
                )
            except Exception:
                return [], {}
        pair_rows = pairs if isinstance(pairs, list) else []
        ticker_rows = tickers if isinstance(tickers, list) else []
        pair_map = {str(x.get("id", "")).upper(): x for x in pair_rows if isinstance(x, dict)}
        universe: list[dict[str, Any]] = []
        quotes: dict[str, dict[str, Any]] = {}
        for x in ticker_rows:
            if not isinstance(x, dict):
                continue
            pair_id = str(x.get("currency_pair", "")).upper()
            base_asset, _, quote_asset = pair_id.partition("_")
            if not base_asset or quote_asset not in {"USDT", "USDC"}:
                continue
            raw = base_asset + quote_asset
            meta = pair_map.get(pair_id, {})
            if str(meta.get("trade_status", "")).lower() not in ("tradable", ""):
                continue
            universe.append({
                "symbol": raw,
                "name": f"{base_asset}/{quote_asset}",
                "market": "crypto",
                "asset_type": "crypto",
                "venue": "gate",
                "currency": quote_asset,
                "metadata": {"base": base_asset, "contract_type": "SPOT", "market_type": "SPOT", "provider": "gate"},
            })
            last = self._float(x.get("last"))
            if last is not None:
                quotes[raw] = {
                    "price": last,
                    "previous_close": self._float(x.get("open_24h")) or last,
                    "change_pct": self._float(x.get("change_percentage")) or 0.0,
                    "volume": self._float(x.get("base_volume")),
                    "quote_volume": self._float(x.get("quote_volume")),
                    "high": self._float(x.get("high_24h")),
                    "low": self._float(x.get("low_24h")),
                    "source": "Gate Spot",
                    "market_data_type": "SPOT",
                    "quote_currency": quote_asset,
                    "base_asset": base_asset,
                    "pair": raw,
                    "contract_type": "SPOT",
                    "market_type": "SPOT",
                    "data_time": None,
                    "quote_status": "live",
                    "provider": "gate",
                }
        return universe, quotes

    async def fallback(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        results = await asyncio.gather(self.okx(), self.bybit(), self.gate(), return_exceptions=True)
        universe: list[dict[str, Any]] = []
        quotes: dict[str, dict[str, Any]] = {}
        seen: set[tuple[str, str]] = set()
        for result in results:
            if isinstance(result, Exception):
                continue
            rows, q = result
            for row in rows:
                key = (row["symbol"], row["venue"])
                if key not in seen:
                    seen.add(key); universe.append(row)
            for symbol, quote in q.items():
                # Prefer the first successful provider; source is retained in the row.
                quotes.setdefault(symbol, quote)
        return universe, quotes

    @staticmethod
    def _float(v: Any) -> float | None:
        try: return float(v) if v not in (None, "") else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _int(v: Any) -> int | None:
        try: return int(v) if v not in (None, "") else None
        except (TypeError, ValueError): return None

    @classmethod
    def _pct(cls, last: Any, prev: Any) -> float:
        a, b = cls._float(last), cls._float(prev)
        return ((a - b) / b * 100.0) if a is not None and b not in (None, 0) else 0.0
