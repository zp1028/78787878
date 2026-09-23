"""Versioned strategy registry shared by live signals and backtests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.quant.features.engine import FeatureSnapshot


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    id: str
    version: str
    name: str
    description: str
    markets: tuple[str, ...] = ("crypto",)
    timeframes: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h", "1d")
    parameters: dict[str, Any] = field(default_factory=dict)
    evaluator: Callable[[FeatureSnapshot, dict[str, Any]], list[dict[str, Any]]] | None = None

    @property
    def key(self) -> str:
        return f"{self.id}@{self.version}"


class StrategyRegistry:
    def __init__(self) -> None:
        self._items: dict[str, StrategyDefinition] = {}

    def register(self, strategy: StrategyDefinition) -> None:
        if strategy.evaluator is None:
            raise ValueError(f"strategy {strategy.key} has no evaluator")
        self._items[strategy.key] = strategy

    def get(self, strategy_id: str, version: str | None = None) -> StrategyDefinition:
        if version:
            key = f"{strategy_id}@{version}"
            if key not in self._items:
                raise KeyError(key)
            return self._items[key]
        candidates = [s for s in self._items.values() if s.id == strategy_id]
        if not candidates:
            raise KeyError(strategy_id)
        return sorted(candidates, key=lambda s: s.version)[-1]

    def list(self) -> list[StrategyDefinition]:
        return sorted(self._items.values(), key=lambda s: (s.id, s.version))

    def evaluate(self, strategy_id: str, snapshot: FeatureSnapshot, params: dict[str, Any] | None = None, version: str | None = None) -> list[dict[str, Any]]:
        strategy = self.get(strategy_id, version)
        if snapshot.timeframe not in strategy.timeframes:
            return []
        merged = dict(strategy.parameters)
        if params:
            merged.update(params)
        return strategy.evaluator(snapshot, merged)  # type: ignore[misc]


def _rsi(snapshot: FeatureSnapshot, p: dict[str, Any]) -> list[dict[str, Any]]:
    v = snapshot.features.get("rsi_14")
    if v is None:
        return []
    low, high = float(p.get("low", 30)), float(p.get("high", 70))
    if v < low:
        return [{"signal_name": "rsi_oversold", "direction": "long", "strength": min(1.0, (low-v)/max(low, 1.0)), "features": {"rsi_14": v}}]
    if v > high:
        return [{"signal_name": "rsi_overbought", "direction": "short", "strength": min(1.0, (v-high)/max(100-high, 1.0)), "features": {"rsi_14": v}}]
    return []


def _macd(snapshot: FeatureSnapshot, p: dict[str, Any]) -> list[dict[str, Any]]:
    h, m, s = snapshot.features.get("macd_hist"), snapshot.features.get("macd"), snapshot.features.get("macd_signal")
    if h is None or m is None or s is None:
        return []
    if h > 0 and m > s:
        return [{"signal_name": "macd_bullish", "direction": "long", "strength": min(1.0, abs(h)*10), "features": {"macd": m, "macd_signal": s, "macd_hist": h}}]
    if h < 0 and m < s:
        return [{"signal_name": "macd_bearish", "direction": "short", "strength": min(1.0, abs(h)*10), "features": {"macd": m, "macd_signal": s, "macd_hist": h}}]
    return []


def _bollinger(snapshot: FeatureSnapshot, p: dict[str, Any]) -> list[dict[str, Any]]:
    v = snapshot.features.get("bb_pct")
    if v is None:
        return []
    if v < 0.05:
        return [{"signal_name": "bb_lower_touch", "direction": "long", "strength": min(1.0, (0.05-v)/0.05), "features": {"bb_pct": v}}]
    if v > 0.95:
        return [{"signal_name": "bb_upper_touch", "direction": "short", "strength": min(1.0, (v-0.95)/0.05), "features": {"bb_pct": v}}]
    return []


def _volume(snapshot: FeatureSnapshot, p: dict[str, Any]) -> list[dict[str, Any]]:
    v = snapshot.features.get("volume_ratio")
    threshold = float(p.get("threshold", 2.0))
    if v is not None and v >= threshold:
        return [{"signal_name": "volume_spike", "direction": "neutral", "strength": min(1.0, v/5.0), "features": {"volume_ratio": v}}]
    return []


def default_registry() -> StrategyRegistry:
    r = StrategyRegistry()
    r.register(StrategyDefinition("rsi", "1.0.0", "RSI Reversion", "RSI oversold/overbought signal", parameters={"low": 30, "high": 70}, evaluator=_rsi))
    r.register(StrategyDefinition("macd", "1.0.0", "MACD Momentum", "MACD histogram directional signal", evaluator=_macd))
    r.register(StrategyDefinition("bollinger", "1.0.0", "Bollinger Reversion", "Bollinger band touch signal", evaluator=_bollinger))
    r.register(StrategyDefinition("volume", "1.0.0", "Volume Anomaly", "Abnormal volume signal", evaluator=_volume))
    return r
