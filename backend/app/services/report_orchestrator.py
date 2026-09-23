from __future__ import annotations
from typing import Any
from app.services.report_registry import REGISTRY, SCENES
from app.services.unified_analysis_report import UnifiedAnalysisReportService
from app.services.market_data_status import MarketDataStatusService
from app.services.report_truth import truth

class ReportOrchestrator:
    def __init__(self):
        self.unified = UnifiedAnalysisReportService()
        self.data_status = MarketDataStatusService()

    async def build(self, report_key: str, symbol: str, market: str, timeframe: str, limit: int = 250) -> dict[str, Any]:
        definition = REGISTRY.get(report_key)
        if not definition:
            raise KeyError(report_key)
        base = await self.unified.build(symbol, market, timeframe, limit)
        status = self.data_status.snapshot()["providers"].get(market, {})
        available = self._availability(definition, market, base, status)
        return {
            "report": {"id": definition.id, "key": definition.key, "name": definition.name, "domain": definition.domain, "priority": definition.priority},
            "instrument": {"symbol": base["symbol"], "market": market, "timeframe": timeframe},
            "generated_at": base.get("generated_at"),
            "data_timestamp": base.get("evidence", {}).get("data_timestamp"),
            "analysis_generated_at": base.get("generated_at"),
            "data_quality": base.get("data_quality", {}),
            "availability": available,
            "summary": self._summary(definition.key, base, available),
            "content": self._content(definition.key, base, available),
            "evidence": base.get("evidence", {}),
            "scenario_analysis": base.get("scenario_analysis", {}),
            "disclaimer": base.get("disclaimer"),
        }

    async def instrument_manifest(self, symbol: str, market: str, timeframe: str) -> dict[str, Any]:
        """Return the complete report catalog bound to one instrument/detail page.

        This does not fabricate report content. It reports whether each of the 32
        report capabilities can currently be generated from the data available for
        this exact symbol, market and timeframe.
        """
        base = await self.unified.build(symbol, market, timeframe, 250)
        status = self.data_status.snapshot()["providers"].get(market, {})
        reports = []
        for definition in REGISTRY.values():
            available = self._availability(definition, market, base, status)
            reports.append({
                "id": definition.id,
                "key": definition.key,
                "name": definition.name,
                "domain": definition.domain,
                "priority": definition.priority,
                "update": definition.update,
                "status": available["status"],
                "reason": available["reason"],
                "source_requirements": list(definition.source_requirements),
            })
        return {
            "analysis_only": True,
            "instrument": {"symbol": base["symbol"], "market": market, "timeframe": timeframe},
            "generated_at": base.get("generated_at"),
            "data_quality": base.get("data_quality", {}),
            "report_count": len(reports),
            "reports": reports,
            "coverage": {
                "available": sum(1 for r in reports if r["status"] == "available"),
                "pending_provider": sum(1 for r in reports if r["status"] == "pending_provider"),
                "unavailable": sum(1 for r in reports if r["status"] == "unavailable"),
            },
        }

    async def instrument_detail(self, symbol: str, market: str, timeframe: str) -> dict[str, Any]:
        """Single request snapshot used by the instrument detail page.

        The response is always scoped to the exact symbol + market + timeframe.
        It contains the live analysis snapshot and the 32-report capability map;
        individual report bodies remain lazy-loaded when the user opens a report.
        """
        base = await self.unified.build(symbol, market, timeframe, 250)
        manifest = await self.instrument_manifest(symbol, market, timeframe)
        return {
            "analysis_only": True,
            "instrument": manifest["instrument"],
            "generated_at": base.get("generated_at"),
            "data_timestamp": base.get("evidence", {}).get("data_timestamp"),
            "analysis_generated_at": base.get("generated_at"),
            "data_quality": base.get("data_quality", {}),
            "unified_analysis": base,
            "report_manifest": manifest,
        }

    def scene(self, scene_key: str) -> dict[str, Any]:
        ids = SCENES.get(scene_key, SCENES["all"])
        return {"scene": scene_key, "report_ids": ids, "reports": [next(v for v in REGISTRY.values() if v.id == i).__dict__ for i in ids]}

    def _availability(self, definition, market, base, status):
        return truth(definition, base, status)

    def _summary(self, key, base, availability):
        if availability["status"] != "available":
            return availability["reason"]
        if key == "one_line_summary":
            return base.get("summary", "")
        if key == "entry_scenario":
            return "已生成多头与空头情景，并给出触发、失效和风险观察条件。"
        if key == "holding_risk":
            return base.get("scenario_analysis", {}).get("risk_notes", "") or "根据当前结构持续观察风险变化。"
        return base.get("summary", "")

    def _content(self, key, base, availability):
        if availability["status"] != "available":
            return {"data_needed": REGISTRY[key].source_requirements, "available_evidence": base.get("evidence", {})}
        if key == "technical":
            return {"technical": base.get("evidence", {}).get("technical", {})}
        if key == "entry_scenario":
            return base.get("scenario_analysis", {})
        if key == "one_line_summary":
            return {"summary": base.get("summary", "")}
        technical = base.get("evidence", {}).get("technical", {})
        enrichment = base.get("evidence", {}).get("market_enrichment", {})
        if key == "smart_alert":
            return {"risk_notes": base.get("scenario_analysis", {}).get("risk_notes", []), "realtime": base.get("realtime_note", ""), "closed_candle_rule": base.get("evidence", {}).get("closed_candle_confirmation_required", True)}
        if key == "realtime_market":
            return {"price": technical.get("last_price"), "timeframe": base.get("timeframe"), "data_timestamp": base.get("evidence", {}).get("data_timestamp"),
            "analysis_generated_at": base.get("generated_at"), "realtime_note": base.get("realtime_note", ""), "data_quality": base.get("data_quality", {})}
        if key == "probability":
            return {"trend": technical.get("trend_label"), "trend_strength": technical.get("trend_strength"), "overbought_count": technical.get("overbought_count", 0), "oversold_count": technical.get("oversold_count", 0), "technical_score": technical.get("technical_score"), "scenario": base.get("scenario_analysis", {})}
        if key == "holding_risk":
            return {"holding": base.get("scenario_analysis", {}).get("holding", {}), "risk_notes": base.get("scenario_analysis", {}).get("risk_notes", []), "invalidation": {"long": base.get("scenario_analysis", {}).get("long", {}).get("invalidation"), "short": base.get("scenario_analysis", {}).get("short", {}).get("invalidation")}}
        if key == "mtf_resonance":
            return {"current_timeframe": base.get("timeframe"), "current": technical, "note": "完整七周期共振通过 /analysis/{symbol}/multi-timeframe 获取并独立重算。"}
        if key in {"divergence", "patterns", "volume_price", "volatility"}:
            return {"technical": technical, "focus": key, "closed_candle_rule": "未收盘K线仅作为实时观察。"}
        if key in {"funding_basis", "money_flow", "sentiment", "correlation", "onchain"}:
            return {"market_enrichment": enrichment, "data_required": REGISTRY[key].source_requirements}
        return {"report": base.get("summary", ""), "technical": technical, "market_enrichment": enrichment}
