"""Shared lifecycle helpers for normalized public crypto WebSocket adapters."""
from __future__ import annotations

import asyncio
import json
import random
import time
from abc import ABC, abstractmethod
from typing import Any

import websockets

from app.core.event_bus import EventBus
from app.models.instrument import ContractType, InstrumentRegistry
from app.models.provider import ProviderHealth, ProviderStatus
from app.providers.base import MarketProvider


class CryptoWsProvider(MarketProvider, ABC):
    """Common reconnect/health/subscription lifecycle for public market feeds."""

    def __init__(self, name: str, url: str, settings: Any, bus: EventBus, instruments: InstrumentRegistry):
        self.name = name
        self.url = url
        self.settings = settings
        self.bus = bus
        self.instruments = instruments
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._ws = None
        self._request_id = 0
        self.subscriptions: set[str] = set()
        self._health = ProviderHealth(name=name, status=ProviderStatus.DOWN)
        self._last_message_mono = 0.0
        self._started_mono = 0.0
        self._backoff = float(getattr(settings, "reconnect_base_seconds", 1.0))

    @property
    def health(self) -> ProviderHealth:
        return self._health

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        for raw in getattr(self.settings, "symbols", []):
            self.instruments.ensure_crypto(raw, venue=self.name, contract_type=ContractType.PERPETUAL)
            self.subscriptions.add(raw.lower())
        self._task = asyncio.create_task(self._run(), name=f"{self.name}-ws")

    async def stop(self) -> None:
        self._stop.set()
        if self._ws:
            await self._ws.close()
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._health.status = ProviderStatus.DOWN

    async def subscribe(self, symbols: list[str]) -> None:
        normalized = {self.normalize_symbol(s) for s in symbols if s}
        for s in normalized:
            self.instruments.ensure_crypto(s.upper(), venue=self.name)
        self.subscriptions.update(normalized)
        if self._ws and not self._ws.closed and normalized:
            await self._send_subscription("subscribe", normalized)

    async def unsubscribe(self, symbols: list[str]) -> None:
        normalized = {self.normalize_symbol(s) for s in symbols if s}
        self.subscriptions.difference_update(normalized)
        if self._ws and not self._ws.closed and normalized:
            await self._send_subscription("unsubscribe", normalized)

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        return symbol.upper().replace("/", "").replace("-", "").replace("_", "")

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if not self._ws or self._ws.closed:
            return
        await self._ws.send(json.dumps(payload, separators=(",", ":")))

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._health.status = ProviderStatus.CONNECTING
                async with websockets.connect(
                    self.url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=4096,
                ) as ws:
                    self._ws = ws
                    self._started_mono = time.monotonic()
                    self._last_message_mono = self._started_mono
                    self._health.status = ProviderStatus.HEALTHY
                    self._backoff = float(getattr(self.settings, "reconnect_base_seconds", 1.0))
                    await self._send_subscription("subscribe", self.subscriptions)

                    while not self._stop.is_set():
                        if time.monotonic() - self._started_mono >= float(getattr(self.settings, "ws_rotate_seconds", 84600.0)):
                            break
                        if time.monotonic() - self._last_message_mono > float(getattr(self.settings, "ws_stale_seconds", 15.0)):
                            self._health.status = ProviderStatus.STALE
                            break
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            await self._heartbeat()
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
            delay = min(self._backoff, float(getattr(self.settings, "reconnect_max_seconds", 30.0)))
            await asyncio.sleep(delay + random.random() * 0.25)
            self._backoff = min(self._backoff * 2, float(getattr(self.settings, "reconnect_max_seconds", 30.0)))

    async def _heartbeat(self) -> None:
        """Provider-specific application heartbeat; websocket ping remains enabled."""
        return

    @abstractmethod
    async def _send_subscription(self, action: str, symbols: set[str]) -> None: ...

    @abstractmethod
    async def _handle_raw(self, raw: str | bytes) -> None: ...
