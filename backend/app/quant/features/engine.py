"""Feature Engine — turns candle history into a FeatureSnapshot.

Keeps a rolling window of closed candles per instrument and computes
a standard set of technical features on every closed bar.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from app.core.event_bus import EventBus
from app.core.events import CandleEvent, FeatureSnapshotEvent
from app.quant.indicators.basic import adx, atr, bollinger, cci, ema, latest, macd, mfi, obv, rsi, sma, stochastic, williams_r, roc
from app.repositories.quant_repo import QuantRepository


@dataclass
class CandleBar:
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_time: int
    close_time: int


@dataclass
class FeatureSnapshot:
    instrument_id: str
    symbol: str
    timeframe: str
    computed_at: int
    available_at: int
    features: dict[str, float | None] = field(default_factory=dict)
    source_close_time: int = 0


class FeatureEngine:
    """Stateful feature calculator driven by CandleEvent."""

    def __init__(
        self,
        bus: EventBus,
        max_bars: int = 300,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        repository: QuantRepository | None = None,
    ):
        self.bus = bus
        self.max_bars = max_bars
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.repository = repository
        # key = (instrument_id, interval)
        self._windows: dict[tuple[str, str], deque[CandleBar]] = defaultdict(
            lambda: deque(maxlen=max_bars)
        )
        self._last_snapshot: dict[tuple[str, str], FeatureSnapshot] = {}

    def subscribe(self) -> None:
        self.bus.subscribe(CandleEvent, self.on_candle)

    async def on_candle(self, event: CandleEvent) -> None:
        if not event.is_closed:
            return
        key = (event.instrument_id, event.interval)
        window = self._windows[key]
        window.append(
            CandleBar(
                open=event.open,
                high=event.high,
                low=event.low,
                close=event.close,
                volume=event.volume,
                open_time=event.open_time,
                close_time=event.close_time,
            )
        )
        snapshot = self._compute(event.instrument_id, event.symbol, event.interval, window)
        if snapshot is None:
            return
        self._last_snapshot[key] = snapshot
        feature_event = FeatureSnapshotEvent(
            instrument_id=snapshot.instrument_id,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            computed_at=snapshot.computed_at,
            available_at=snapshot.available_at,
            features=snapshot.features,
            source_close_time=snapshot.source_close_time,
        )
        if self.repository is not None:
            await self.repository.save_feature(feature_event)
        await self.bus.publish(feature_event)

    def get_latest(self, instrument_id: str, interval: str) -> FeatureSnapshot | None:
        return self._last_snapshot.get((instrument_id, interval))

    def _compute(
        self,
        instrument_id: str,
        symbol: str,
        interval: str,
        window: deque[CandleBar],
    ) -> FeatureSnapshot | None:
        if len(window) < 5:
            return None
        closes = [b.close for b in window]
        volumes = [b.volume for b in window]
        highs = [b.high for b in window]
        lows = [b.low for b in window]

        rsi_series = rsi(closes, self.rsi_period)
        macd_line, signal_line, hist = macd(
            closes, self.macd_fast, self.macd_slow, self.macd_signal
        )
        bb_mid, bb_upper, bb_lower = bollinger(closes, self.bb_period)
        sma20 = sma(closes, 20)
        sma50 = sma(closes, 50)
        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        atr14 = atr(highs, lows, closes, 14)
        adx14 = adx(highs, lows, closes, 14)
        stoch_k, stoch_d = stochastic(highs, lows, closes, 14)
        cci20 = cci(highs, lows, closes, 20)
        willr14 = williams_r(highs, lows, closes, 14)
        roc12 = roc(closes, 12)
        obv_s = obv(closes, volumes)
        mfi14 = mfi(highs, lows, closes, volumes, 14)

        last_close = closes[-1]
        last_vol = volumes[-1]
        avg_vol_20 = None
        if len(volumes) >= 20:
            avg_vol_20 = sum(volumes[-20:]) / 20.0

        features: dict[str, float | None] = {
            "close": last_close,
            "high": highs[-1],
            "low": lows[-1],
            "volume": last_vol,
            "rsi_14": latest(rsi_series),
            "macd": latest(macd_line),
            "macd_signal": latest(signal_line),
            "macd_hist": latest(hist),
            "bb_mid": latest(bb_mid),
            "bb_upper": latest(bb_upper),
            "bb_lower": latest(bb_lower),
            "sma_20": latest(sma20),
            "sma_50": latest(sma50),
            "ema_12": latest(ema12),
            "ema_26": latest(ema26),
            "volume_sma_20": avg_vol_20,
            "atr_14": latest(atr14),
            "adx_14": latest(adx14),
            "stoch_k": latest(stoch_k),
            "stoch_d": latest(stoch_d),
            "cci_20": latest(cci20),
            "williams_r_14": latest(willr14),
            "roc_12": latest(roc12),
            "obv": latest(obv_s),
            "mfi_14": latest(mfi14),
        }

        # derived
        if features["bb_upper"] and features["bb_lower"] and features["bb_mid"]:
            width = features["bb_upper"] - features["bb_lower"]
            features["bb_width"] = width
            if width > 0:
                features["bb_pct"] = (last_close - features["bb_lower"]) / width
        if avg_vol_20 and avg_vol_20 > 0:
            features["volume_ratio"] = last_vol / avg_vol_20

        now = int(time.time() * 1000)
        # For live closed candles, available_at == close_time (PIT-safe for live)
        available_at = window[-1].close_time
        return FeatureSnapshot(
            instrument_id=instrument_id,
            symbol=symbol,
            timeframe=interval,
            computed_at=now,
            available_at=available_at,
            features=features,
            source_close_time=window[-1].close_time,
        )

    def snapshot_dict(self, snap: FeatureSnapshot) -> dict[str, Any]:
        return {
            "instrument_id": snap.instrument_id,
            "symbol": snap.symbol,
            "timeframe": snap.timeframe,
            "computed_at": snap.computed_at,
            "available_at": snap.available_at,
            "features": snap.features,
            "source_close_time": snap.source_close_time,
        }
