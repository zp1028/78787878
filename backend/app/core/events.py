"""Canonical event contracts for the Smart Trader EventBus.

All real-time and historical processing flows through these typed events.
Timestamps:
  - source_timestamp : exchange / origin time (ms)
  - received_at      : when the backend first saw the message (ms)
  - processed_at     : when the normalizer finished (ms) — optional
  - available_at     : earliest time this data was legally usable (PIT)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Market data events
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class MarketTickEvent:
    """Best bid/ask + last trade snapshot (bookTicker / ticker)."""

    instrument_id: str
    symbol: str
    bid: float | None
    ask: float | None
    last: float | None
    bid_size: float | None
    ask_size: float | None
    source_timestamp: int
    received_at: int
    processed_at: int
    venue: str = "binance"


@dataclass(slots=True)
class ProviderSwitchEvent:
    """Emitted when the normalized downstream crypto stream changes venue."""

    provider: str
    previous_provider: str | None
    reason: str
    changed_at: int


@dataclass(slots=True)
class TradeEvent:
    instrument_id: str
    symbol: str
    price: float
    quantity: float
    is_buyer_maker: bool | None
    source_timestamp: int
    received_at: int
    venue: str = "binance"


@dataclass(slots=True)
class CandleEvent:
    instrument_id: str
    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_time: int
    close_time: int
    is_closed: bool
    source_timestamp: int
    received_at: int
    venue: str = "binance"


@dataclass(slots=True)
class OrderBookEvent:
    """Full or incremental order book snapshot."""

    instrument_id: str
    symbol: str
    bids: list[tuple[float, float]]  # (price, size)
    asks: list[tuple[float, float]]
    source_timestamp: int
    received_at: int
    is_snapshot: bool = True
    venue: str = "binance"


@dataclass(slots=True)
class FundingRateEvent:
    instrument_id: str
    symbol: str
    funding_rate: float
    next_funding_time: int | None
    source_timestamp: int
    received_at: int
    venue: str = "binance"


@dataclass(slots=True)
class OpenInterestEvent:
    instrument_id: str
    symbol: str
    open_interest: float
    open_interest_value: float | None
    source_timestamp: int
    received_at: int
    venue: str = "binance"


# ---------------------------------------------------------------------------
# External / alternative data
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class NewsEvent:
    instrument_ids: list[str]
    title: str
    summary: str | None
    url: str | None
    source: str
    published_at: int          # publication time (ms)
    available_at: int          # PIT: when it became available
    sentiment: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MacroEvent:
    series_id: str
    value: float
    observation_date: str
    published_at: int
    available_at: int
    source: str = "fred"
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Quant / signal layer
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FeatureSnapshotEvent:
    """PIT-safe feature snapshot emitted after a closed candle is processed."""

    instrument_id: str
    symbol: str
    timeframe: str
    computed_at: int
    available_at: int
    features: dict[str, float | None] = field(default_factory=dict)
    source_close_time: int = 0


@dataclass(slots=True)
class SignalEvent:
    instrument_id: str
    symbol: str
    signal_name: str
    direction: str              # "long" | "short" | "flat" | "neutral"
    strength: float             # 0.0 – 1.0
    timeframe: str
    features: dict[str, float] = field(default_factory=dict)
    source_timestamp: int = 0
    generated_at: int = 0


@dataclass(slots=True)
class AttentionEvent:
    instrument_id: str
    symbol: str
    score: float
    reasons: list[str] = field(default_factory=list)
    regime: str | None = None
    generated_at: int = 0


@dataclass(slots=True)
class ObservationTriggeredEvent:
    """User-defined observation node fired (price level, indicator, etc.)."""

    instrument_id: str
    symbol: str
    observation_id: str
    trigger_type: str           # "price" | "indicator" | "composite"
    trigger_value: float
    current_value: float
    triggered_at: int


# ---------------------------------------------------------------------------
# AI layer
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AIAnalysisStartedEvent:
    instrument_id: str
    symbol: str
    analysis_id: str
    trigger: str                # "manual" | "attention" | "observation" | "schedule"
    started_at: int


@dataclass(slots=True)
class AIAnalysisCompletedEvent:
    instrument_id: str
    symbol: str
    analysis_id: str
    result: dict[str, Any]      # structured AnalysisResult
    completed_at: int
    duration_ms: int
    data_quality: float = 0.0


# ---------------------------------------------------------------------------
# Portfolio / risk / execution (stubs for later phases)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PositionChangedEvent:
    instrument_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float | None
    unrealized_pnl: float | None
    changed_at: int


@dataclass(slots=True)
class RiskChangedEvent:
    account_id: str
    risk_level: str
    metrics: dict[str, float]
    changed_at: int


@dataclass(slots=True)
class OrderSubmittedEvent:
    order_id: str
    instrument_id: str
    side: str
    quantity: float
    order_type: str
    submitted_at: int


@dataclass(slots=True)
class OrderFilledEvent:
    order_id: str
    instrument_id: str
    fill_price: float
    fill_quantity: float
    filled_at: int


@dataclass(slots=True)
class OrderRejectedEvent:
    order_id: str
    instrument_id: str
    reason: str
    rejected_at: int


# ---------------------------------------------------------------------------
# Backward-compatible aliases (so existing tests / code keep working)
# ---------------------------------------------------------------------------

# Old names used in P0-01
MarketTick = MarketTickEvent
