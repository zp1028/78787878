"""AI Orchestrator — builds structured AnalysisResult from quant context.

V1 uses deterministic TechnicalAgent (features + signals). Hooks are ready
for real LLM agents (News / Sentiment / Macro / Bull-Bear Debate) later.
Never emits free-text BUY/SELL as the sole decision — only structured result.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.ai.agents.technical import analyze_technical
from app.ai.agents.research import analyze_money_flow, analyze_sentiment, debate, AgentFinding
from app.ai.agents.contextual import analyze_news, analyze_macro, analyze_onchain
from app.ai.guard import PostAIGuard
from app.quant.regime.engine import RegimeEngine
from app.ai.models import AnalysisResult, EvidenceItem, Scenario
from app.ai.calibration import load_calibration, scenario_probabilities
from app.core.event_bus import EventBus
from app.core.events import (
    AIAnalysisCompletedEvent,
    AIAnalysisStartedEvent,
    AttentionEvent,
    ObservationTriggeredEvent,
    SignalEvent,
)
from app.quant.attention.engine import AttentionEngine
from app.quant.features.engine import FeatureEngine
from app.quant.signals.engine import SignalEngine
from app.repositories.analysis_repo import AnalysisRepository


class AIOrchestrator:
    def __init__(
        self,
        bus: EventBus,
        feature_engine: FeatureEngine,
        signal_engine: SignalEngine,
        attention_engine: AttentionEngine | None = None,
        *,
        auto_on_attention: bool = True,
        attention_threshold: float = 0.55,
        auto_on_observation: bool = True,
    ):
        self.bus = bus
        self.features = feature_engine
        self.signals = signal_engine
        self.attention = attention_engine
        self.auto_on_attention = auto_on_attention
        self.attention_threshold = attention_threshold
        self.auto_on_observation = auto_on_observation
        self._history: dict[str, list[AnalysisResult]] = {}
        self._latest: dict[str, AnalysisResult] = {}
        self.repository = AnalysisRepository()
        self.regime_engine = RegimeEngine()
        self.guard = PostAIGuard()

    def subscribe(self) -> None:
        if self.auto_on_attention:
            self.bus.subscribe(AttentionEvent, self.on_attention)
        if self.auto_on_observation:
            self.bus.subscribe(ObservationTriggeredEvent, self.on_observation)

    async def on_attention(self, event: AttentionEvent) -> None:
        if event.score < self.attention_threshold:
            return
        await self.run(
            instrument_id=event.instrument_id,
            symbol=event.symbol,
            trigger="attention",
            timeframe="1m",
            extra_context={"attention_score": event.score, "regime": event.regime},
        )

    async def on_observation(self, event: ObservationTriggeredEvent) -> None:
        await self.run(
            instrument_id=event.instrument_id,
            symbol=event.symbol,
            trigger="observation",
            timeframe="1m",
            extra_context={
                "observation_id": event.observation_id,
                "trigger_value": event.trigger_value,
                "current_value": event.current_value,
            },
        )

    async def run(
        self,
        instrument_id: str,
        symbol: str,
        *,
        trigger: str = "manual",
        timeframe: str = "1m",
        extra_context: dict[str, Any] | None = None,
    ) -> AnalysisResult:
        analysis_id = str(uuid.uuid4())
        started = int(time.time() * 1000)

        await self.bus.publish(
            AIAnalysisStartedEvent(
                instrument_id=instrument_id,
                symbol=symbol,
                analysis_id=analysis_id,
                trigger=trigger,
                started_at=started,
            )
        )

        snap = self.features.get_latest(instrument_id, timeframe)
        # collect recent signals for this instrument from signal engine cache
        recent_signals: list[SignalEvent] = []
        for name in (
            "rsi_oversold",
            "rsi_overbought",
            "macd_bullish",
            "macd_bearish",
            "bb_lower_touch",
            "bb_upper_touch",
            "volume_spike",
        ):
            s = self.signals.get_latest(instrument_id, name)
            if s:
                recent_signals.append(s)

        technical, bull, bear, evidence, trend, conf = analyze_technical(snap, recent_signals)
        feature_map = snap.features if snap else {}
        money = analyze_money_flow(feature_map)
        sentiment_agent = analyze_sentiment(feature_map)
        news_agent = analyze_news(feature_map)
        macro_agent = analyze_macro(feature_map)
        onchain_agent = analyze_onchain(feature_map)
        technical_score = float(technical.get("score")) if technical and technical.get("score") is not None else 0.0
        technical_finding = AgentFinding("TechnicalAgent", trend, technical_score, conf, bull + bear)
        debate_finding = debate(technical_finding, money, sentiment_agent)
        regime_result = self.regime_engine.classify(feature_map)
        trend = debate_finding.stance if debate_finding.stance != "neutral" else trend
        # This is evidence completeness, not predictive probability.
        conf = max(conf, debate_finding.confidence)
        evidence.extend([
            EvidenceItem(source="money_flow", agent=money.agent, summary="; ".join(money.reasons), confidence=money.confidence, raw={"score": money.score, "stance": money.stance}),
            EvidenceItem(source="sentiment", agent=sentiment_agent.agent, summary="; ".join(sentiment_agent.reasons), confidence=sentiment_agent.confidence, raw={"score": sentiment_agent.score, "stance": sentiment_agent.stance}),
            EvidenceItem(source="debate", agent=debate_finding.agent, summary="independent findings reconciled", confidence=debate_finding.confidence, raw={"score": debate_finding.score, "stance": debate_finding.stance}),
            EvidenceItem(source="news", agent=news_agent.agent, summary="; ".join(news_agent.reasons), confidence=news_agent.confidence, raw={"score": news_agent.score, "stance": news_agent.stance}),
            EvidenceItem(source="macro", agent=macro_agent.agent, summary="; ".join(macro_agent.reasons), confidence=macro_agent.confidence, raw={"score": macro_agent.score, "stance": macro_agent.stance}),
            EvidenceItem(source="onchain", agent=onchain_agent.agent, summary="; ".join(onchain_agent.reasons), confidence=onchain_agent.confidence, raw={"score": onchain_agent.score, "stance": onchain_agent.stance}),
        ])

        # support / resistance from bollinger if present
        support: list[float] = []
        resistance: list[float] = []
        if snap:
            bl = snap.features.get("bb_lower")
            bu = snap.features.get("bb_upper")
            mid = snap.features.get("bb_mid")
            if bl:
                support.append(float(bl))
            if mid:
                support.append(float(mid))
                resistance.append(float(mid))
            if bu:
                resistance.append(float(bu))

        # data quality: based on feature completeness
        data_quality = 0.0
        if snap:
            keys = ["close", "rsi_14", "macd", "bb_pct", "volume_ratio"]
            present = sum(1 for k in keys if snap.features.get(k) is not None)
            data_quality = present / len(keys)

        regime = regime_result.name
        if self.attention:
            att = self.attention.get_latest(instrument_id)
            if att:
                regime = att.regime or regime
                evidence.append(
                    EvidenceItem(
                        source="feature",
                        agent="AttentionEngine",
                        summary=f"attention_score={att.score}, regime={att.regime}",
                        confidence=att.score,
                        raw={"score": att.score, "reasons": att.reasons},
                    )
                )

        # Scenario probability is never seeded with fixed percentages.  It is
        # derived from completed historical feedback when available.  Until
        # there are real outcomes, the API returns null rather than pretending
        # that a rule such as RSI>70 has a known probability.
        calibration = load_calibration()
        p_bull, p_base, p_bear, calibration_meta = scenario_probabilities(
            directional_score=technical_score, calibration=calibration
        )
        scenarios = [
            Scenario(name="bull", thesis="; ".join(bull) if bull else "暂无明显多头依据", probability=p_bull),
            Scenario(name="base", thesis="当前证据不足以给出经过历史校准的方向性概率。", probability=p_base),
            Scenario(name="bear", thesis="; ".join(bear) if bear else "暂无明显空头依据", probability=p_bear),
        ]

        completed = int(time.time() * 1000)
        guard = self.guard.evaluate(confidence=conf, data_quality=data_quality)
        result = AnalysisResult(
            analysis_id=analysis_id,
            instrument_id=instrument_id,
            symbol=symbol,
            timestamp=completed,
            market_state=regime or "unknown",
            trend=trend,
            technical=technical,
            money_flow={"volume_ratio": technical.get("volume_ratio"), "agent_score": money.score, "stance": money.stance},
            sentiment={"agent_score": sentiment_agent.score, "stance": sentiment_agent.stance},
            macro={"agent_score": macro_agent.score, "stance": macro_agent.stance},
            bull_case=bull,
            bear_case=bear,
            support=support,
            resistance=resistance,
            scenarios=scenarios,
            risk={
                "note": "AI output is advisory only; Risk Engine must validate any action",
                "post_ai_guard": {"allowed": guard.allowed, "risk_level": guard.risk_level, "reasons": guard.reasons, "limits": guard.limits},
                "data_quality": data_quality, "calibration": calibration_meta, "regime_confidence": regime_result.confidence, "regime_reasons": regime_result.reasons,
            },
            confidence=round(max(0.0, min(1.0, conf * data_quality)), 3),
            data_quality=round(data_quality, 3),
            evidence=evidence,
            trigger=trigger,
            regime=regime,
        )

        self._latest[instrument_id] = result
        try:
            await self.repository.save_analysis(result.model_dump(), [e.model_dump() for e in evidence], started_at=started, completed_at=completed, trigger=trigger, data_quality=result.data_quality)
        except Exception:
            # Analysis availability must not be taken down by persistence outages.
            pass
        self._history.setdefault(instrument_id, []).append(result)
        # keep last 50 per instrument
        if len(self._history[instrument_id]) > 50:
            self._history[instrument_id] = self._history[instrument_id][-50:]

        await self.bus.publish(
            AIAnalysisCompletedEvent(
                instrument_id=instrument_id,
                symbol=symbol,
                analysis_id=analysis_id,
                result=result.model_dump(),
                completed_at=completed,
                duration_ms=completed - started,
                data_quality=result.data_quality,
            )
        )
        return result

    def get_latest(self, instrument_id: str) -> AnalysisResult | None:
        return self._latest.get(instrument_id)

    def get_history(self, instrument_id: str, limit: int = 20) -> list[AnalysisResult]:
        return list(reversed(self._history.get(instrument_id, [])[-limit:]))
