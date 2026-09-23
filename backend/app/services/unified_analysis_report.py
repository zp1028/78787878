from __future__ import annotations
from typing import Any
from app.services.analysis_report import HumanAnalysisReportService
from app.ai.advice import build_indicator_only_advice
from app.data.market_klines import fetch_market_klines
from app.quant.indicators.analysis import analyze_bars
from app.services.analysis_enrichment import AnalysisEnrichmentService

class UnifiedAnalysisReportService:
    """One explainable report contract for every supported market."""
    def __init__(self):
        self.human = HumanAnalysisReportService()
        self.enrichment = AnalysisEnrichmentService()

    async def build(self, symbol: str, market: str, timeframe: str, limit: int = 250) -> dict[str, Any]:
        report = await self.human.build(symbol, market, timeframe, limit)
        bars = await fetch_market_klines(symbol, market, timeframe, limit)
        technical = analyze_bars(
            instrument_id=f"{market}:{symbol.upper().replace('/', '').replace('-', '')}",
            symbol=report["symbol"], timeframe=timeframe, market=market, bars=bars,
        )
        advice = build_indicator_only_advice(technical, None).model_dump()
        enrichment = await self.enrichment.enrich(symbol, market, timeframe)
        return {
            **report,
            "analysis_version": "P35-unified-truth-v3",
            "provenance": {
                "analysis_only": True,
                "data_source_rule": "Only values present in the current provider snapshot may enter a report.",
                "missing_data_rule": "Missing provider data is represented as unavailable/pending_provider; no default market value is substituted.",
                "probability_rule": "Probability is displayed only when the walk-forward research status is calibrated.",
            },
            "scenario_analysis": {
                "long": advice["long_entry"],
                "short": advice["short_entry"],
                "holding": advice["position"],
                "risk_notes": advice["risk_notes"],
            },
            "evidence": {
                "technical": technical.model_dump(),
                "market_enrichment": enrichment,
                "data_timestamp": report.get("last_close_time"),
                "analysis_generated_at": report.get("generated_at"),
                "closed_candle_confirmation_required": True,
                "intrabar_vs_closed": {
                    "live_context": "当前行情可变，未收盘K线仅作为实时观察证据",
                    "confirmed_context": "结构性突破/跌破需等待对应周期收盘确认",
                },
            },
            "disclaimer": "仅用于市场研究与情景分析，不构成投资建议；不提供模拟、账户连接或下单功能。",
        }
