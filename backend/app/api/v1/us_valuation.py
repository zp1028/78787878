from fastapi import APIRouter, HTTPException, Query
from app.services.us_valuation import UsValuationService

router = APIRouter(tags=["valuation"])
service = UsValuationService()

@router.get("/valuation/us/{ticker}")
def us_valuation(ticker: str, price: float | None = Query(default=None, gt=0), quote_time: str | None = None):
    try:
        return service.build(ticker, price, quote_time)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"US valuation unavailable: {exc}") from exc
