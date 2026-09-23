from fastapi import APIRouter, HTTPException
from app.services.us_fundamentals import UsFundamentalsService

router = APIRouter(tags=["fundamentals"])
service = UsFundamentalsService()

@router.get("/fundamentals/us/ticker/{ticker}")
def us_fundamentals_by_ticker(ticker: str):
    try:
        return service.latest(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SEC fundamentals unavailable: {exc}") from exc
