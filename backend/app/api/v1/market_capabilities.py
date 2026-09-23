from fastapi import APIRouter
from app.services.market_capabilities import MarketCapabilityService

router = APIRouter(tags=["market-capabilities"])
service = MarketCapabilityService()

@router.get("/market-capabilities")
def market_capabilities():
    return service.snapshot()

@router.get("/market-capabilities/{market}")
def market_capability(market: str):
    return service.get(market)
