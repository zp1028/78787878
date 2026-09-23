"""Attention Engine — ranks instruments by dynamic importance.

Combines recent signals, volatility proxies, volume spikes and simple
regime hints into an AttentionEvent. This is the feed that later drives
AI depth routing and the Discovery page ranking.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from app.core.event_bus import EventBus
from app.core.events import AttentionEvent, CandleEvent, SignalEvent


@dataclass
class _InstrumentState:
    last_close: float | None = None
    last_volume: float | None = None
    volume_sma: float | None = None
    rsi: float | None = None
    recent_signals: deque[SignalEvent] = field(default_factory=lambda: deque(maxlen=20))
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    regime: str | None = None
    updated_at: int = 0


class AttentionEngine:
    def __init__(
        self,
        bus: EventBus,
        *,
        signal_weight: float = 0.45,
        volume_weight: float = 0.25,
        volatility_weight: float = 0.20,
        rsi_extreme_weight: float = 0.10,
        decay_seconds: float = 300.0,
    ):
        self.bus = bus
        self.signal_weight = signal_weight
        self.volume_weight = volume_weight
        self.volatility_weight = volatility_weight
        self.rsi_extreme_weight = rsi_extreme_weight
        self.decay_seconds = decay_seconds
        self._state: dict[str, _InstrumentState] = defaultdict(_InstrumentState)
        self._last_attention: dict[str, AttentionEvent] = {}

    def subscribe(self) -> None:
        self.bus.subscribe(SignalEvent, self.on_signal)
        self.bus.subscribe(CandleEvent, self.on_candle)

    async def on_signal(self, event: SignalEvent) -> None:
        st = self._state[event.instrument_id]
        st.recent_signals.append(event)
        await self._recompute_and_publish(event.instrument_id, event.symbol)

    async def on_candle(self, event: CandleEvent) -> None:
        if not event.is_closed:
            return
        st = self._state[event.instrument_id]
        # crude volatility proxy from candle range
        prev = st.last_close
        st.last_close = event.close
        st.last_volume = event.volume
        # volume_sma is filled if FeatureEngine already computed; we approximate here
        if st.volume_sma is None:
            st.volume_sma = event.volume
        else:
            st.volume_sma = st.volume_sma * 0.9 + event.volume * 0.1
        await self._recompute_and_publish(event.instrument_id, event.symbol, prev_close=prev)

    async def _recompute_and_publish(
        self,
        instrument_id: str,
        symbol: str,
        prev_close: float | None = None,
    ) -> None:
        st = self._state[instrument_id]
        now = int(time.time() * 1000)
        reasons: list[str] = []
        score = 0.0

        # --- signal component ---
        sig_score = 0.0
        if st.recent_signals:
            # decay older signals
            weighted = 0.0
            total_w = 0.0
            for s in st.recent_signals:
                age_s = max(0.0, (now - s.generated_at) / 1000.0)
                w = max(0.0, 1.0 - age_s / self.decay_seconds)
                weighted += s.strength * w
                total_w += w
                if w > 0.3:
                    reasons.append(f"{s.signal_name}:{s.direction}@{s.strength:.2f}")
            if total_w > 0:
                sig_score = min(1.0, weighted / total_w)
        score += self.signal_weight * sig_score

        # --- volume component ---
        vol_score = 0.0
        if st.last_volume is not None and st.volume_sma and st.volume_sma > 0:
            ratio = st.last_volume / st.volume_sma
            if ratio >= 1.5:
                vol_score = min(1.0, (ratio - 1.0) / 3.0)
                reasons.append(f"volume_ratio={ratio:.2f}")
        score += self.volume_weight * vol_score

        # --- volatility component (range vs last close) ---
        vola_score = 0.0
        if prev_close and st.last_close and prev_close > 0:
            move = abs(st.last_close - prev_close) / prev_close
            if move >= 0.005:  # >= 0.5%
                vola_score = min(1.0, move / 0.03)
                reasons.append(f"move={move*100:.2f}%")
        score += self.volatility_weight * vola_score

        # --- RSI extreme (if we saw it via signals features) ---
        rsi_score = 0.0
        for s in st.recent_signals:
            if "rsi_14" in s.features:
                rsi = s.features["rsi_14"]
                st.rsi = rsi
                if rsi <= 30 or rsi >= 70:
                    rsi_score = min(1.0, abs(rsi - 50) / 50)
                    reasons.append(f"rsi={rsi:.1f}")
                break
        score += self.rsi_extreme_weight * rsi_score

        score = round(min(1.0, max(0.0, score)), 4)

        # simple regime hint
        regime = "normal"
        if vola_score >= 0.6:
            regime = "high_volatility"
        elif sig_score >= 0.6 and vol_score >= 0.4:
            regime = "momentum"
        elif st.rsi is not None and (st.rsi < 35 or st.rsi > 65):
            regime = "mean_reversion_zone"

        st.score = score
        st.reasons = reasons[:8]
        st.regime = regime
        st.updated_at = now

        event = AttentionEvent(
            instrument_id=instrument_id,
            symbol=symbol,
            score=score,
            reasons=list(st.reasons),
            regime=regime,
            generated_at=now,
        )
        self._last_attention[instrument_id] = event
        await self.bus.publish(event)

    def get_latest(self, instrument_id: str) -> AttentionEvent | None:
        return self._last_attention.get(instrument_id)

    def ranking(self, limit: int = 20) -> list[AttentionEvent]:
        items = sorted(
            self._last_attention.values(),
            key=lambda e: e.score,
            reverse=True,
        )
        return items[:limit]
