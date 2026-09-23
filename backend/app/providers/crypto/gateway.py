"""Multi-provider normalized public crypto WebSocket gateway."""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from app.core.event_bus import EventBus
from app.core.events import ProviderSwitchEvent
from app.models.instrument import InstrumentRegistry
from app.models.provider import ProviderHealth, ProviderStatus
from app.providers.base import MarketProvider
from app.providers.crypto.binance.ws import BinanceWsClient
from app.providers.crypto.bybit.ws import BybitWsClient
from app.providers.crypto.okx.ws import OkxWsClient


class CryptoWsGateway(MarketProvider):
    """Expose one normalized downstream stream and fail over its upstream provider.

    The Android app never chooses an exchange. The gateway keeps the configured
    provider order, preserves subscriptions during a switch, and exposes the
    actual active venue in health/events.
    """

    DEFAULT_ORDER = ("binance", "okx", "bybit")

    def __init__(self, settings: Any, bus: EventBus, instruments: InstrumentRegistry):
        self.settings = settings
        self.bus = bus
        self.instruments = instruments
        self._providers: dict[str, MarketProvider] = {
            "binance": BinanceWsClient(settings, bus, instruments),
            "okx": OkxWsClient(settings, bus, instruments),
            "bybit": BybitWsClient(settings, bus, instruments),
        }
        self._active_name: str | None = None
        self._index = 0
        self._subscriptions: set[str] = set()
        self._switch_lock = asyncio.Lock()
        self._monitor_task: asyncio.Task | None = None
        self._started = False
        self._bad_since: float | None = None

    @property
    def order(self) -> tuple[str, ...]:
        raw = os.getenv("SMART_TRADER_CRYPTO_PROVIDER_ORDER", "").strip()
        requested = tuple(x.strip().lower() for x in raw.split(",") if x.strip()) if raw else self.DEFAULT_ORDER
        valid = tuple(x for x in requested if x in self._providers)
        return valid or self.DEFAULT_ORDER

    @property
    def active_provider(self) -> MarketProvider | None:
        return self._providers.get(self._active_name) if self._active_name else None

    @property
    def active_name(self) -> str | None:
        return self._active_name

    @property
    def subscriptions(self) -> set[str]:
        return set(self._subscriptions)

    @property
    def health(self) -> ProviderHealth:
        provider = self.active_provider
        if provider is None:
            return ProviderHealth(name="crypto-gateway", status=ProviderStatus.DOWN, last_error="no active provider")
        h = provider.health.model_copy(deep=True)
        h.name = provider.health.name
        return h

    def health_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "provider": name,
                "active": name == self._active_name,
                **self._providers[name].health.model_dump(),
            }
            for name in self.order
        ]

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._index = 0
        self._bad_since = None
        await self._activate(self.order[0])
        self._monitor_task = asyncio.create_task(self._monitor(), name="crypto-ws-gateway-monitor")

    async def stop(self) -> None:
        self._started = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        for provider in self._providers.values():
            try:
                await provider.stop()
            except Exception:
                pass
        self._active_name = None

    async def subscribe(self, symbols: list[str]) -> None:
        self._subscriptions.update(s.upper().replace("/", "").replace("-", "") for s in symbols if s)
        if self.active_provider and symbols:
            await self.active_provider.subscribe(symbols)

    async def unsubscribe(self, symbols: list[str]) -> None:
        normalized = {s.upper().replace("/", "").replace("-", "") for s in symbols if s}
        self._subscriptions.difference_update(normalized)
        if self.active_provider and symbols:
            await self.active_provider.unsubscribe(symbols)

    async def _activate(self, name: str) -> None:
        if name not in self._providers:
            return
        lock = getattr(self, "_switch_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            self._switch_lock = lock
        async with lock:
            if self._active_name == name:
                return
            previous = self._active_name
            old = self.active_provider
            if old:
                try:
                    await old.stop()
                except Exception:
                    pass
            self._active_name = name
            self._bad_since = None
            provider = self._providers[name]
            try:
                await provider.start()
                if self._subscriptions:
                    await provider.subscribe(sorted(self._subscriptions))
            except Exception:
                # Do not leave the gateway advertising a provider that failed to start.
                self._active_name = previous
                raise
            bus = getattr(self, "bus", None)
            if bus is not None:
                await bus.publish(ProviderSwitchEvent(
                    provider=name,
                    previous_provider=previous,
                    reason="initial" if previous is None else "failover",
                    changed_at=int(time.time() * 1000),
                ))

    async def _switch_next(self) -> None:
        order = self.order
        if not order:
            return
        current = self._active_name
        if current in order:
            self._index = (order.index(current) + 1) % len(order)
        else:
            self._index = 0
        await self._activate(order[self._index])

    async def _monitor(self) -> None:
        grace = float(getattr(self.settings, "ws_failover_grace_seconds", 8.0))
        while self._started:
            await asyncio.sleep(2.0)
            provider = self.active_provider
            if provider is None:
                await self._activate(self.order[0])
                continue
            status = provider.health.status
            if status == ProviderStatus.HEALTHY:
                self._bad_since = None
                continue
            if self._bad_since is None:
                self._bad_since = time.monotonic()
            if time.monotonic() - self._bad_since >= grace:
                await self._switch_next()


__all__ = ["CryptoWsGateway"]
