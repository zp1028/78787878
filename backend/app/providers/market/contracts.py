from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol

@dataclass(slots=True)
class ProviderCapability:
    market: str
    realtime: bool = False
    historical: bool = False
    orderbook: bool = False
    fundamentals: bool = False
    news: bool = False

class MarketDataProvider(Protocol):
    name: str
    capabilities: ProviderCapability
    async def health(self) -> dict: ...
    async def fetch_candles(self, symbol: str, timeframe: str, limit: int = 300) -> list[dict]: ...

@dataclass(slots=True)
class ProviderHealth:
    name: str
    healthy: bool
    latency_ms: float | None = None
    last_error: str | None = None
    metadata: dict = field(default_factory=dict)
