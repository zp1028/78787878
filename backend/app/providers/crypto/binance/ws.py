"""Binance USD-M Futures combined WebSocket market data adapter.

Normalizes every message into the Unified Market Model events and publishes
them on the shared EventBus. Never exposes raw Binance payloads upwards.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any

import websockets

from app.core.event_bus import EventBus
from app.core.events import (
    CandleEvent,
    FundingRateEvent,
    MarketTickEvent,
    TradeEvent,
)
from app.models.instrument import ContractType, InstrumentRegistry
from app.models.provider import ProviderHealth, ProviderStatus
from app.providers.base import MarketProvider


class BinanceWsClient(MarketProvider):
    """Configurable Binance combined market-stream client."""

    def __init__(
        self,
        settings: Any,
        bus: EventBus,
        instruments: InstrumentRegistry | None = None,
    ):
        self.settings = settings
        self.bus = bus
        self.instruments = instruments or InstrumentRegistry()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._ws = None
        self._request_id = 0
        self.subscriptions: set[str] = set()
        self._health = ProviderHealth(name="binance", status=ProviderStatus.DOWN)
        self._last_message_mono = 0.0
        self._started_mono = 0.0
        self._backoff = float(getattr(settings, "reconnect_base_seconds", 1.0))
        self._last_prices: dict[str, float] = {}
        self._mark_prices: dict[str, float] = {}

    @property
    def health(self) -> ProviderHealth:
        return self._health

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        # pre-register instruments
        for raw in self.settings.symbols:
            self.instruments.ensure_crypto(raw, venue="binance", contract_type=ContractType.PERPETUAL)
            self.subscriptions.add(raw.lower())
        self._task = asyncio.create_task(self._run(), name="binance-ws")

    async def stop(self) -> None:
        self._stop.set()
        if self._ws:
            await self._ws.close()
        if self._task:
            await self._task
        self._health.status = ProviderStatus.DOWN

    async def subscribe(self, symbols: list[str]) -> None:
        normalized = {s.lower() for s in symbols}
        for s in normalized:
            self.instruments.ensure_crypto(s.upper(), venue="binance")
        self.subscriptions.update(normalized)
        if self._ws and not self._ws.closed:
            await self._send("SUBSCRIBE", self._streams_for(normalized))

    async def unsubscribe(self, symbols: list[str]) -> None:
        normalized = {s.lower() for s in symbols}
        self.subscriptions.difference_update(normalized)
        if self._ws and not self._ws.closed:
            await self._send("UNSUBSCRIBE", self._streams_for(normalized))

    def _streams_for(self, symbols: set[str] | list[str]) -> list[str]:
        streams: list[str] = []
        for symbol in symbols:
            streams += [
                f"{symbol}@ticker",
                f"{symbol}@trade",
                f"{symbol}@bookTicker",
                f"{symbol}@markPrice@1s",
                f"{symbol}@kline_{self.settings.binance_kline_interval}",
            ]
        return streams

    async def _send(self, method: str, params: list[str]) -> None:
        if not self._ws or self._ws.closed or not params:
            return
        self._request_id += 1
        await self._ws.send(
            json.dumps(
                {
                    "method": method,
                    "params": params,
                    "id": self._request_id,
                }
            )
        )

    def _instrument_id(self, raw_symbol: str) -> str:
        inst = self.instruments.ensure_crypto(raw_symbol, venue="binance")
        return inst.instrument_id

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._health.status = ProviderStatus.CONNECTING
                async with websockets.connect(
                    self.settings.binance_ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=4096,
                ) as ws:
                    self._ws = ws
                    self._started_mono = time.monotonic()
                    self._last_message_mono = self._started_mono
                    self._health.status = ProviderStatus.HEALTHY
                    self._backoff = self.settings.reconnect_base_seconds
                    await self._send("SUBSCRIBE", self._streams_for(self.subscriptions))

                    while not self._stop.is_set():
                        if time.monotonic() - self._started_mono >= self.settings.ws_rotate_seconds:
                            break
                        if time.monotonic() - self._last_message_mono > self.settings.ws_stale_seconds:
                            self._health.status = ProviderStatus.STALE
                            break
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            continue
                        self._last_message_mono = time.monotonic()
                        self._health.last_message = int(time.time() * 1000)
                        await self._handle_raw(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._health.status = ProviderStatus.RECONNECTING
                self._health.error_count += 1
                self._health.last_error = str(exc)
            finally:
                self._ws = None

            if self._stop.is_set():
                break
            self._health.status = ProviderStatus.RECONNECTING
            self._health.reconnect_count += 1
            delay = min(self._backoff, self.settings.reconnect_max_seconds)
            await asyncio.sleep(delay + random.random() * 0.25)
            self._backoff = min(self._backoff * 2, self.settings.reconnect_max_seconds)

    async def _handle_raw(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        message = json.loads(raw)
        if "result" in message and "id" in message:
            return
        payload = message.get("data", message)
        event_type = payload.get("e")
        received = int(time.time() * 1000)
        source_ts = int(payload.get("E", received))
        processed = int(time.time() * 1000)

        if event_type == "24hrTicker":
            symbol = payload["s"].upper()
            last = float(payload["c"])
            self._last_prices[symbol] = last
            iid = self._instrument_id(symbol)
            await self.bus.publish(
                MarketTickEvent(
                    instrument_id=iid,
                    symbol=symbol,
                    bid=None,
                    ask=None,
                    last=last,
                    bid_size=None,
                    ask_size=None,
                    source_timestamp=source_ts,
                    received_at=received,
                    processed_at=processed,
                    venue="binance",
                )
            )

        elif event_type == "trade":
            symbol = payload["s"].upper()
            iid = self._instrument_id(symbol)
            await self.bus.publish(
                TradeEvent(
                    instrument_id=iid,
                    symbol=symbol,
                    price=float(payload["p"]),
                    quantity=float(payload["q"]),
                    is_buyer_maker=payload.get("m"),
                    source_timestamp=source_ts,
                    received_at=received,
                    venue="binance",
                )
            )

        elif event_type == "bookTicker":
            symbol = payload["s"].upper()
            iid = self._instrument_id(symbol)
            await self.bus.publish(
                MarketTickEvent(
                    instrument_id=iid,
                    symbol=symbol,
                    bid=float(payload["b"]),
                    ask=float(payload["a"]),
                    last=self._last_prices.get(symbol),
                    bid_size=float(payload["B"]),
                    ask_size=float(payload["A"]),
                    source_timestamp=source_ts,
                    received_at=received,
                    processed_at=processed,
                    venue="binance",
                )
            )

        elif event_type == "markPriceUpdate":
            symbol = payload["s"].upper()
            iid = self._instrument_id(symbol)
            mark = float(payload["p"])
            self._mark_prices[symbol] = mark
            await self.bus.publish(
                FundingRateEvent(
                    instrument_id=iid,
                    symbol=symbol,
                    funding_rate=float(payload.get("r", 0.0)),
                    next_funding_time=int(payload.get("T")) if payload.get("T") is not None else None,
                    source_timestamp=source_ts,
                    received_at=received,
                    venue="binance",
                )
            )
            await self.bus.publish(
                MarketTickEvent(
                    instrument_id=iid,
                    symbol=symbol,
                    bid=None,
                    ask=None,
                    last=mark,
                    bid_size=None,
                    ask_size=None,
                    source_timestamp=source_ts,
                    received_at=received,
                    processed_at=processed,
                    venue="binance",
                )
            )

        elif event_type == "kline":
            k = payload["k"]
            symbol = payload["s"].upper()
            iid = self._instrument_id(symbol)
            await self.bus.publish(
                CandleEvent(
                    instrument_id=iid,
                    symbol=symbol,
                    interval=k["i"],
                    open=float(k["o"]),
                    high=float(k["h"]),
                    low=float(k["l"]),
                    close=float(k["c"]),
                    volume=float(k["v"]),
                    open_time=int(k["t"]),
                    close_time=int(k["T"]),
                    is_closed=bool(k["x"]),
                    source_timestamp=source_ts,
                    received_at=received,
                    venue="binance",
                )
            )
