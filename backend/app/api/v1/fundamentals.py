from fastapi import APIRouter, HTTPException, Query
from app.services.sec_fundamentals import SecFundamentalsService

router = APIRouter(tags=["fundamentals"])
service = SecFundamentalsService()

@router.get("/fundamentals/us/{cik}")
def us_fundamentals(cik: str):
    try:
        return service.latest(cik)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SEC fundamentals unavailable: {exc}") from exc
