from fastapi import APIRouter, HTTPException
from app.services.hk_provider import HKMarketProvider

router = APIRouter(tags=["hk-market-data"])
provider = HKMarketProvider()

@router.get("/hk/data-status")
def hk_data_status():
    return provider.status()

@router.get("/hk/universe")
def hk_universe():
    try:
        return {"analysis_only": True, "data": provider.universe()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"HK universe unavailable: {exc}") from exc

@router.get("/hk/quote/{symbol}")
def hk_quote(symbol: str):
    try:
        return {"analysis_only": True, "symbol": symbol.upper(), "data": provider.quote(symbol.upper())}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"HK quote unavailable: {exc}") from exc
