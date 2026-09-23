from fastapi import APIRouter, Query, HTTPException
from app.services.market_structure import MarketStructureService

router = APIRouter(tags=["market-structure"])
service = MarketStructureService()

@router.get("/analysis/{symbol}/structure")
async def structure_analysis(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m"), limit: int = Query(200, ge=30, le=500)):
    try:
        return await service.build(symbol, market, timeframe, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"market structure failed: {exc}") from exc
