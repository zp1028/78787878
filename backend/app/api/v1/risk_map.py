from fastapi import APIRouter, Query, HTTPException
from app.services.risk_map import RiskMapService

router = APIRouter(tags=["risk-map"])
service = RiskMapService()

@router.get("/analysis/{symbol}/risk-map")
async def risk_map(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m"), limit: int = Query(160, ge=30, le=200)):
    try:
        return await service.build(symbol, market, timeframe, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"risk map failed: {exc}") from exc
