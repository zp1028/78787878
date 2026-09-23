from __future__ import annotations
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.main import ai_orchestrator, feature_engine, signal_engine
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.quant_repo import QuantRepository

router = APIRouter(tags=["replay"])
repo = AnalysisRepository()
quant_repo = QuantRepository()

class ReplayCreate(BaseModel):
    instrument_id: str
    symbol: str
    timeframe: str = "1m"
    analysis_time: int

@router.post("/replay")
async def create_replay(body: ReplayCreate):
    # Replay must use persisted PIT snapshots, never the current in-memory state.
    snap_row = quant_repo.latest_feature_at(body.instrument_id, body.timeframe, body.analysis_time)
    signal_rows = quant_repo.signals_at(body.instrument_id, body.analysis_time)
    signals = [r.__dict__ for r in signal_rows]
    ai = next((x for x in repo.history(body.instrument_id, 200) if x.get("timestamp", 0) <= body.analysis_time), None)
    sid = str(uuid.uuid4())
    feature_payload = None
    if snap_row:
        feature_payload = {"available_at": snap_row.available_at, "computed_at": snap_row.computed_at, "features": snap_row.features}
    evidence = ai.get("evidence", []) if ai else []
    repo.save_replay(sid, body.instrument_id, body.analysis_time, {"symbol": body.symbol, "timeframe": body.timeframe}, feature_payload, signals, ai, evidence, ai.get("risk") if ai else None)
    return repo.get_replay(sid)

@router.get("/replay/{snapshot_id}")
def get_replay(snapshot_id: str):
    item = repo.get_replay(snapshot_id)
    if not item: raise HTTPException(404, "replay not found")
    return item
