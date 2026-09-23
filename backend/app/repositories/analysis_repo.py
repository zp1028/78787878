from __future__ import annotations
import asyncio
from typing import Any
from sqlalchemy import select, desc
from app.db.models import AIAnalysisRow, AnalysisReplayRow
from app.db.session import get_session

class AnalysisRepository:
    async def save_analysis(self, result: dict[str, Any], evidence: list[dict[str, Any]], *, started_at: int, completed_at: int, trigger: str, data_quality: float) -> None:
        await asyncio.to_thread(self._save_analysis, result, evidence, started_at, completed_at, trigger, data_quality)

    @staticmethod
    def _save_analysis(result, evidence, *, started_at, completed_at, trigger, data_quality):
        with get_session() as db:
            row = db.scalar(select(AIAnalysisRow).where(AIAnalysisRow.analysis_id == result["analysis_id"]))
            values = dict(instrument_id=result["instrument_id"], trigger=trigger, started_at=started_at,
                          completed_at=completed_at, duration_ms=completed_at-started_at,
                          data_quality=data_quality, result=result, evidence=evidence,
                          available_at=result.get("timestamp", completed_at))
            if row is None:
                db.add(AIAnalysisRow(analysis_id=result["analysis_id"], **values))
            else:
                for k,v in values.items(): setattr(row,k,v)

    def history(self, instrument_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with get_session() as db:
            rows = db.scalars(select(AIAnalysisRow).where(AIAnalysisRow.instrument_id == instrument_id).order_by(desc(AIAnalysisRow.available_at)).limit(max(1,min(limit,200)))).all()
            return [r.result for r in rows]

    def save_replay(self, snapshot_id: str, instrument_id: str, analysis_time: int, market_snapshot: dict[str,Any], feature_snapshot: dict[str,Any] | None, signals: list[Any], ai_analysis: dict[str,Any] | None, evidence: list[Any], risk: dict[str,Any] | None) -> None:
        from datetime import datetime, timezone
        with get_session() as db:
            row = db.scalar(select(AnalysisReplayRow).where(AnalysisReplayRow.snapshot_id == snapshot_id))
            values = dict(instrument_id=instrument_id, analysis_time=analysis_time, market_snapshot=market_snapshot,
                          feature_snapshot=feature_snapshot, signals=signals, ai_analysis=ai_analysis,
                          evidence=evidence, risk=risk, created_at=datetime.now(timezone.utc))
            if row is None: db.add(AnalysisReplayRow(snapshot_id=snapshot_id, **values))
            else:
                for k,v in values.items(): setattr(row,k,v)

    def get_replay(self, snapshot_id: str) -> dict[str,Any] | None:
        with get_session() as db:
            r = db.scalar(select(AnalysisReplayRow).where(AnalysisReplayRow.snapshot_id == snapshot_id))
            if not r: return None
            return {"snapshot_id":r.snapshot_id,"instrument_id":r.instrument_id,"analysis_time":r.analysis_time,
                    "market_snapshot":r.market_snapshot,"feature_snapshot":r.feature_snapshot,"signals":r.signals,
                    "ai_analysis":r.ai_analysis,"evidence":r.evidence,"risk":r.risk,"outcome":r.outcome}
