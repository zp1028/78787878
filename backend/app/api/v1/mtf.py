from fastapi import APIRouter, Query, HTTPException
from app.services.mtf_analysis import MTFAnalysisService

router = APIRouter(tags=["mtf-analysis"])
service = MTFAnalysisService()

@router.get("/analysis/{symbol}/multi-timeframe")
async def multi_timeframe_analysis(symbol: str, market: str = Query("crypto"), current: str = Query("15m"), limit: int = Query(200, ge=60, le=500)):
    try:
        return await service.build(symbol, market, current, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"multi-timeframe analysis failed: {exc}") from exc
