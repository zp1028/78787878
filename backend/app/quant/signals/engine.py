"""Signal Engine backed by the versioned StrategyRegistry."""
from __future__ import annotations

import time

from app.core.event_bus import EventBus
from app.core.events import FeatureSnapshotEvent, SignalEvent
from app.quant.features.engine import FeatureEngine, FeatureSnapshot
from app.quant.strategies import StrategyRegistry, default_registry
from app.repositories.quant_repo import QuantRepository


class SignalEngine:
    def __init__(self, bus: EventBus, feature_engine: FeatureEngine, repository: QuantRepository | None = None, registry: StrategyRegistry | None = None):
        self.bus = bus
        self.features = feature_engine
        self.repository = repository
        self.registry = registry or default_registry()
        self._last_signals: dict[str, SignalEvent] = {}

    def subscribe(self) -> None:
        self.bus.subscribe(FeatureSnapshotEvent, self.on_feature)

    async def on_feature(self, event: FeatureSnapshotEvent) -> None:
        snap = FeatureSnapshot(event.instrument_id, event.symbol, event.timeframe, event.computed_at, event.available_at, event.features, event.source_close_time)
        for strategy in self.registry.list():
            for item in self.registry.evaluate(strategy.id, snap):
                sig = SignalEvent(
                    instrument_id=snap.instrument_id,
                    symbol=snap.symbol,
                    signal_name=item["signal_name"],
                    direction=item["direction"],
                    strength=round(min(1.0, max(0.0, float(item["strength"]))), 4),
                    timeframe=snap.timeframe,
                    features=item.get("features", {}),
                    source_timestamp=snap.source_close_time,
                    generated_at=int(time.time() * 1000),
                )
                self._last_signals[f"{sig.instrument_id}:{sig.signal_name}"] = sig
                if self.repository is not None:
                    await self.repository.save_signal(sig)
                await self.bus.publish(sig)

    def get_latest(self, instrument_id: str, signal_name: str) -> SignalEvent | None:
        return self._last_signals.get(f"{instrument_id}:{signal_name}")
