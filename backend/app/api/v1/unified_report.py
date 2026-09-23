from fastapi import APIRouter, HTTPException, Query
from app.services.unified_analysis_report import UnifiedAnalysisReportService

router = APIRouter(tags=["unified-report"])
service = UnifiedAnalysisReportService()

@router.get("/unified-report/{symbol}")
async def unified_report(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m"), limit: int = Query(250, ge=60, le=500)):
    try:
        return await service.build(symbol, market, timeframe, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"unified report failed: {exc}") from exc
