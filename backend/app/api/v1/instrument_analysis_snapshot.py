from fastapi import APIRouter, HTTPException, Query
from app.services.instrument_analysis_snapshot import InstrumentAnalysisSnapshotService

router = APIRouter(tags=["instrument-analysis"])
service = InstrumentAnalysisSnapshotService()


@router.get("/instrument/{market}/{symbol}/analysis")
async def instrument_analysis(
    market: str,
    symbol: str,
    timeframe: str = Query("15m"),
    limit: int = Query(250, ge=60, le=500),
):
    try:
        return await service.build(symbol, market, timeframe, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"instrument analysis failed: {exc}") from exc
