from fastapi import APIRouter, Query, HTTPException
from app.services.scenario_engine import ScenarioEngine
router = APIRouter(tags=["scenario-analysis"])
service = ScenarioEngine()
@router.get("/analysis/{symbol}/scenarios")
async def scenarios_analysis(symbol: str, market: str = Query("crypto"), timeframe: str = Query("15m"), limit: int = Query(200, ge=30, le=500), holding_side: str | None = Query(None), entry_price: float | None = Query(None, gt=0)):
    try:
        return await service.build(symbol, market, timeframe, limit, holding_side=holding_side, entry_price=entry_price)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"scenario analysis failed: {exc}") from exc
