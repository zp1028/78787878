"""Observation Node Engine — user-defined condition triggers.

When a price (or later indicator) level is crossed, emit
ObservationTriggeredEvent so the rest of the pipeline can re-run
Feature → Signal → Attention → (future AI).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.event_bus import EventBus
from app.core.events import MarketTickEvent, ObservationTriggeredEvent


@dataclass
class ObservationNode:
    observation_id: str
    instrument_id: str
    symbol: str
    trigger_type: str  # "price"
    trigger_value: float
    direction: str  # "above" | "below" | "cross"
    is_active: bool = True
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    last_triggered_at: int | None = None
    # internal: last known price for cross detection
    _last_price: float | None = field(default=None, repr=False)


class ObservationEngine:
    def __init__(self, bus: EventBus, cooldown_ms: int = 60_000):
        self.bus = bus
        self.cooldown_ms = cooldown_ms
        # instrument_id -> list of nodes
        self._nodes: dict[str, list[ObservationNode]] = {}
        self._by_id: dict[str, ObservationNode] = {}

    def subscribe(self) -> None:
        self.bus.subscribe(MarketTickEvent, self.on_tick)

    def add(
        self,
        instrument_id: str,
        symbol: str,
        trigger_value: float,
        *,
        direction: str = "cross",
        trigger_type: str = "price",
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        observation_id: str | None = None,
    ) -> ObservationNode:
        oid = observation_id or str(uuid.uuid4())
        node = ObservationNode(
            observation_id=oid,
            instrument_id=instrument_id,
            symbol=symbol,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            direction=direction,
            user_id=user_id,
            metadata=metadata or {},
        )
        self._nodes.setdefault(instrument_id, []).append(node)
        self._by_id[oid] = node
        return node

    def remove(self, observation_id: str) -> bool:
        node = self._by_id.pop(observation_id, None)
        if not node:
            return False
        lst = self._nodes.get(node.instrument_id, [])
        self._nodes[node.instrument_id] = [n for n in lst if n.observation_id != observation_id]
        return True

    def list_for(self, instrument_id: str) -> list[ObservationNode]:
        return list(self._nodes.get(instrument_id, []))

    def list_all(self) -> list[ObservationNode]:
        return list(self._by_id.values())

    async def on_tick(self, event: MarketTickEvent) -> None:
        price = event.last
        if price is None:
            # fall back to mid if available
            if event.bid is not None and event.ask is not None:
                price = (event.bid + event.ask) / 2.0
            else:
                return
        nodes = self._nodes.get(event.instrument_id, [])
        if not nodes:
            return
        now = int(time.time() * 1000)
        for node in nodes:
            if not node.is_active:
                continue
            if node.last_triggered_at and (now - node.last_triggered_at) < self.cooldown_ms:
                continue
            if self._should_trigger(node, price):
                node.last_triggered_at = now
                node._last_price = price
                await self.bus.publish(
                    ObservationTriggeredEvent(
                        instrument_id=node.instrument_id,
                        symbol=node.symbol,
                        observation_id=node.observation_id,
                        trigger_type=node.trigger_type,
                        trigger_value=node.trigger_value,
                        current_value=price,
                        triggered_at=now,
                    )
                )
            else:
                node._last_price = price

    def _should_trigger(self, node: ObservationNode, price: float) -> bool:
        tv = node.trigger_value
        if node.direction == "above":
            return price >= tv and (node._last_price is None or node._last_price < tv)
        if node.direction == "below":
            return price <= tv and (node._last_price is None or node._last_price > tv)
        # cross: either direction
        if node._last_price is None:
            return False
        prev = node._last_price
        return (prev < tv <= price) or (prev > tv >= price)
