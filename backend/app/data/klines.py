"""Fetch OHLCV klines for an arbitrary timeframe (crypto first).

Uses Binance public REST so indicator analysis can switch period without
depending only on the live 1m WebSocket window.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

# Binance USD-M futures interval whitelist
SUPPORTED_INTERVALS = {
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "12h",
    "1d",
    "1w",
}

# Binance Spot public klines endpoint (data-api.binance.vision reachable in
# restricted networks; fapi.binance.com is the original USD-M futures source).
BINANCE_SPOT_KLINES = "https://data-api.binance.vision/api/v3/klines"

# Small TTL cache so several analysis endpoints (indicators/structure/scenarios/
# risk-map/unified) share one upstream fetch per symbol+interval+limit instead
# of hammering the public API with near-identical requests.
_KLINES_CACHE: dict[tuple[str, str, int], tuple[float, list[dict[str, Any]]]] = {}
_KLINES_TTL_SECONDS = 12.0


async def fetch_binance_klines(
    symbol: str,
    interval: str = "15m",
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Returns list of bars:
      open, high, low, close, volume, open_time, close_time
    symbol: BTCUSDT or BTC/USDT
    """
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"unsupported interval {interval}; use one of {sorted(SUPPORTED_INTERVALS)}")

    raw_sym = symbol.upper().replace("/", "").replace("-", "")
    limit = max(10, min(limit, 1500))

    key = (raw_sym, interval, limit)
    now = time.monotonic()
    hit = _KLINES_CACHE.get(key)
    if hit and now - hit[0] < _KLINES_TTL_SECONDS:
        return hit[1]

    params = {"symbol": raw_sym, "interval": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(BINANCE_SPOT_KLINES, params=params)
        resp.raise_for_status()
        data = resp.json()

    bars: list[dict[str, Any]] = []
    for row in data:
        # [open_time, o, h, l, c, vol, close_time, ...]
        bars.append(
            {
                "open_time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "close_time": int(row[6]),
            }
        )
    _KLINES_CACHE[key] = (time.monotonic(), bars)
    return bars
