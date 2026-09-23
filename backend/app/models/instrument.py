"""Unified Market Model — core data contract for the entire system.

All upper layers (Feature, Signal, AI, Risk, Backtest, Android) only see
these structures. Provider-specific formats never leak upwards.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AssetType(StrEnum):
    CRYPTO = "crypto"
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    FUTURE = "future"
    OPTION = "option"
    FOREX = "forex"
    MACRO = "macro"
    PREDICTION = "prediction"
    COMMODITY = "commodity"


class ContractType(StrEnum):
    SPOT = "spot"
    PERPETUAL = "perpetual"
    DELIVERY = "delivery"
    OPTION = "option"
    UNKNOWN = "unknown"


class Instrument(BaseModel):
    """Canonical instrument identity used everywhere above the provider layer."""

    instrument_id: str = Field(
        ...,
        description="Stable internal id, e.g. 'binance:BTCUSDT' or 'futu:00700.HK'",
    )
    symbol: str = Field(..., description="Display / unified symbol, e.g. 'BTC/USDT', 'AAPL', '00700.HK'")
    market: str = Field(..., description="Logical market, e.g. 'crypto', 'us', 'hk'")
    asset_type: AssetType
    venue: str = Field(..., description="Exchange / broker, e.g. 'binance', 'okx', 'futu', 'yahoo'")
    quote_currency: str | None = None
    base_currency: str | None = None
    contract_type: ContractType = ContractType.UNKNOWN
    tick_size: float | None = None
    lot_size: float | None = None
    timezone: str = "UTC"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class InstrumentRegistry:
    """In-memory registry for P0-02. Will be backed by PostgreSQL later."""

    def __init__(self) -> None:
        self._by_id: dict[str, Instrument] = {}
        self._by_symbol_venue: dict[tuple[str, str], Instrument] = {}

    def register(self, instrument: Instrument) -> None:
        self._by_id[instrument.instrument_id] = instrument
        key = (instrument.symbol.upper(), instrument.venue.lower())
        self._by_symbol_venue[key] = instrument

    def get(self, instrument_id: str) -> Instrument | None:
        return self._by_id.get(instrument_id)

    def get_by_symbol(self, symbol: str, venue: str) -> Instrument | None:
        return self._by_symbol_venue.get((symbol.upper(), venue.lower()))

    def list_all(self) -> list[Instrument]:
        return list(self._by_id.values())

    def ensure_crypto(
        self,
        symbol: str,
        venue: str = "binance",
        contract_type: ContractType = ContractType.PERPETUAL,
        quote_currency: str = "USDT",
    ) -> Instrument:
        """Convenience helper used by the Binance adapter."""
        normalized = symbol.upper().replace("/", "")
        instrument_id = f"{venue}:{normalized}"
        existing = self.get(instrument_id)
        if existing:
            return existing

        # crude base extraction for common quote currencies
        base = normalized
        for q in ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH"):
            if normalized.endswith(q) and len(normalized) > len(q):
                base = normalized[: -len(q)]
                quote_currency = q
                break

        inst = Instrument(
            instrument_id=instrument_id,
            symbol=f"{base}/{quote_currency}",
            market="crypto",
            asset_type=AssetType.CRYPTO,
            venue=venue,
            quote_currency=quote_currency,
            base_currency=base,
            contract_type=contract_type,
            timezone="UTC",
            metadata={"raw_symbol": normalized},
        )
        self.register(inst)
        return inst
