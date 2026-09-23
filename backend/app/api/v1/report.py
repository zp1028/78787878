from fastapi import APIRouter, HTTPException, Query
from app.services.analysis_report import HumanAnalysisReportService

router = APIRouter(tags=["analysis-report"])
service = HumanAnalysisReportService()

@router.get("/analysis-report/{symbol}")
async def get_analysis_report(
    symbol: str,
    market: str = Query("crypto"),
    timeframe: str = Query("15m"),
    limit: int = Query(250, ge=60, le=500),
):
    try:
        return await service.build(symbol, market, timeframe, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"analysis report failed: {exc}") from exc
