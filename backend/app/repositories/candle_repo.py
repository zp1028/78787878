"""Persistent OHLCV cache and gap-aware candle recovery."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from sqlalchemy import select

from app.core.events import CandleEvent
from app.services.crypto_provider_gateway import CryptoProviderGateway
from app.db.models import CandleRow
from app.db.session import get_session


class CandleRepository:
    async def save_event(self, event: CandleEvent) -> None:
        if not event.is_closed:
            return
        await asyncio.to_thread(
            self._upsert,
            event.instrument_id, event.symbol, event.venue, event.interval,
            event.open_time, event.close_time, event.open, event.high,
            event.low, event.close, event.volume, event.source_timestamp,
            event.received_at,
        )

    @staticmethod
    def _upsert(
        instrument_id: str, symbol: str, venue: str, timeframe: str,
        open_time: int, close_time: int, open_: float, high: float,
        low: float, close: float, volume: float, source_timestamp: int,
        available_at: int,
    ) -> None:
        with get_session() as db:
            row = db.scalar(select(CandleRow).where(
                CandleRow.instrument_id == instrument_id,
                CandleRow.timeframe == timeframe,
                CandleRow.open_time == open_time,
            ))
            if row is None:
                row = CandleRow(
                    instrument_id=instrument_id, symbol=symbol, venue=venue,
                    timeframe=timeframe, open_time=open_time, close_time=close_time,
                    open=open_, high=high, low=low, close=close, volume=volume,
                    source_timestamp=source_timestamp, available_at=available_at,
                    source_version="crypto-provider-rest/ws-v2",
                )
                db.add(row)
            else:
                row.close_time = close_time
                row.open = open_
                row.high = high
                row.low = low
                row.close = close
                row.volume = volume
                row.source_timestamp = source_timestamp
                row.available_at = available_at

    async def upsert_bars(
        self, instrument_id: str, symbol: str, timeframe: str,
        bars: list[dict[str, Any]], venue: str = "binance",
    ) -> int:
        if not bars:
            return 0
        await asyncio.to_thread(self._upsert_many, instrument_id, symbol, timeframe, bars, venue)
        return len(bars)

    @staticmethod
    def _upsert_many(instrument_id: str, symbol: str, timeframe: str,
                     bars: list[dict[str, Any]], venue: str) -> None:
        now = int(time.time() * 1000)
        with get_session() as db:
            for b in bars:
                row = db.scalar(select(CandleRow).where(
                    CandleRow.instrument_id == instrument_id,
                    CandleRow.timeframe == timeframe,
                    CandleRow.open_time == int(b["open_time"]),
                ))
                values = dict(
                    symbol=symbol, venue=venue, timeframe=timeframe,
                    open_time=int(b["open_time"]), close_time=int(b["close_time"]),
                    open=float(b["open"]), high=float(b["high"]), low=float(b["low"]),
                    close=float(b["close"]), volume=float(b["volume"]),
                    source_timestamp=int(b["close_time"]), available_at=now,
                    source_version="crypto-provider-rest-v2",
                )
                if row is None:
                    db.add(CandleRow(instrument_id=instrument_id, **values))
                else:
                    for k, v in values.items():
                        setattr(row, k, v)

    async def latest(self, instrument_id: str, timeframe: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._latest, instrument_id, timeframe)

    @staticmethod
    def _latest(instrument_id: str, timeframe: str) -> dict[str, Any] | None:
        with get_session() as db:
            row = db.scalar(select(CandleRow).where(
                CandleRow.instrument_id == instrument_id,
                CandleRow.timeframe == timeframe,
            ).order_by(CandleRow.open_time.desc()).limit(1))
            if row is None:
                return None
            return {"open_time": row.open_time, "close_time": row.close_time,
                    "open": row.open, "high": row.high, "low": row.low,
                    "close": row.close, "volume": row.volume}


class CandleRecoveryService:
    """Detect missing bars after WS gaps and backfill them from REST."""
    def __init__(self, bus, instruments, symbols: list[str], intervals: list[str], crypto_gateway: CryptoProviderGateway | None = None):
        self.bus = bus
        self.instruments = instruments
        self.symbols = symbols
        self.intervals = intervals
        self.repo = CandleRepository()
        self.crypto_gateway = crypto_gateway or CryptoProviderGateway()

    def subscribe(self) -> None:
        self.bus.subscribe(CandleEvent, self._on_candle)

    async def _on_candle(self, event: CandleEvent) -> None:
        await self.repo.save_event(event)
        if not event.is_closed:
            return
        # A closed kline is the canonical boundary. A REST check is only done
        # when the stored previous candle is not immediately adjacent.
        await self._recover_if_gap(event)

    async def _recover_if_gap(self, event: CandleEvent) -> None:
        previous = await asyncio.to_thread(self._previous_open_time, event.instrument_id, event.interval, event.open_time)
        if previous is None:
            return
        step = _interval_ms(event.interval)
        if event.open_time - previous <= step:
            return
        bars, provider = await self.crypto_gateway.fetch_klines(
            event.symbol, event.interval, limit=min(1500, max(20, int((event.open_time - previous) / step) + 5))
        )
        missing = [b for b in bars if previous < int(b["open_time"]) < event.open_time]
        await self.repo.upsert_bars(event.instrument_id, event.symbol, event.interval, missing, venue=provider)

    @staticmethod
    def _previous_open_time(instrument_id: str, timeframe: str, before: int) -> int | None:
        with get_session() as db:
            return db.scalar(select(CandleRow.open_time).where(
                CandleRow.instrument_id == instrument_id,
                CandleRow.timeframe == timeframe,
                CandleRow.open_time < before,
            ).order_by(CandleRow.open_time.desc()).limit(1))

    async def bootstrap(self, limit: int = 300) -> None:
        async def one(symbol: str, interval: str) -> None:
            try:
                bars, provider = await self.crypto_gateway.fetch_klines(symbol, interval, limit=limit)
                inst = self.instruments.ensure_crypto(symbol, venue=provider)
                await self.repo.upsert_bars(inst.instrument_id, symbol, interval, bars, venue=provider)
            except Exception as exc:
                print(f"[candle-recovery] {symbol} {interval}: {exc}")

        await asyncio.gather(
            *(one(symbol, interval) for symbol in self.symbols for interval in self.intervals),
            return_exceptions=True,
        )


def _interval_ms(interval: str) -> int:
    units = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
    n = int(interval[:-1])
    return n * units[interval[-1]]
