from __future__ import annotations
from typing import Any

from app.services.instrument_snapshot import InstrumentSnapshotService
from app.services.market_capabilities import MarketCapabilityService
from app.services.unified_analysis_report import UnifiedAnalysisReportService


class InstrumentAnalysisSnapshotService:
    """Single read-only contract used by instrument detail screens.

    It combines the current market snapshot, capability truth and the unified
    explainable analysis without introducing any account/order/execution state.
    """

    def __init__(self) -> None:
        self.snapshot_service = InstrumentSnapshotService()
        self.capability_service = MarketCapabilityService()
        self.report_service = UnifiedAnalysisReportService()

    async def build(self, symbol: str, market: str, timeframe: str, limit: int = 250) -> dict[str, Any]:
        snapshot = await self.snapshot_service.snapshot(symbol, market, timeframe)
        capabilities = await self.capability_service.get(market)
        report = await self.report_service.build(symbol, market, timeframe, limit)
        return {
            "analysis_only": True,
            "read_only": True,
            "instrument": {"symbol": symbol, "market": market, "timeframe": timeframe},
            "snapshot": snapshot,
            "capabilities": capabilities,
            "analysis": report,
            "data_contract": "instrument-analysis-v1",
        }
