from fastapi import APIRouter, HTTPException, Query

from app.services.market_universe import MarketUniverseService
from app.services.market_coverage import MarketCoverageService
from app.services.market_data_status import MarketDataStatusService
from app.services.crypto_provider_gateway import CryptoProviderGateway

router = APIRouter(tags=["markets"])
universe = MarketUniverseService()
coverage = MarketCoverageService(universe)
data_status = MarketDataStatusService()
_crypto_gateway = CryptoProviderGateway()

async def _crypto_quotes() -> dict[str, dict[str, float]]:
    rows = await _crypto_gateway.market_rows()
    return {str(x.get("symbol", "")).upper().replace("/", ""): x for x in rows if x.get("quote_status") == "live"}



@router.get("/markets")
async def markets(
    market: str | None = Query(None, description="crypto/us/hk/commodities"),
    q: str | None = Query(None, description="symbol/name search"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=1000000),
    sort: str = Query("symbol", description="symbol|name"),
):
    # Crypto is sourced entirely from the unified gateway so the discovered
    # instrument and its quote always come from the same live provider.
    market_key = market.lower() if market else None
    if market_key == "crypto":
        raw_items = await _crypto_gateway.market_rows()
        items = [dict(x) for x in raw_items]
    elif market_key == "us":
        items = [x.__dict__.copy() for x in await universe.us()]
    elif market_key == "hk":
        items = [x.__dict__.copy() for x in await universe.hk()]
    elif market_key == "commodities":
        items = [x.__dict__.copy() for x in await universe.commodities()]
    else:
        import asyncio
        from dataclasses import asdict

        groups = await asyncio.gather(
            _crypto_gateway.market_rows(), universe.us(), universe.hk(), universe.commodities()
        )
        items = [
            item
            for group in groups
            for item in (
                group
                if group and isinstance(group[0], dict)
                else [asdict(x) if hasattr(x, "__dataclass_fields__") else dict(x) for x in group]
            )
        ]

    if q:
        needle = q.lower()
        items = [
            x for x in items
            if needle in str(x.get("symbol", "")).lower()
            or needle in str(x.get("name", x.get("symbol", ""))).lower()
        ]

    if sort == "name":
        items = sorted(items, key=lambda x: (str(x.get("name", "")).lower(), str(x.get("symbol", "")).lower()))
    else:
        items = sorted(items, key=lambda x: str(x.get("symbol", "")).lower())

    total = len(items)
    page = items[offset:offset + limit]
    rows = []
    for row in page:
        row = dict(row)
        row.setdefault("analysis_only", True)
        row.setdefault("quote_status", "live" if row.get("price") is not None else "provider_unavailable")
        rows.append(row)

    return {
        "analysis_only": True,
        "count": len(rows),
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "markets": rows,
    }




@router.get("/markets/providers/health")
async def crypto_provider_health():
    """Return the real crypto market provider health used by /markets.

    This is intentionally separate from the generic provider registry because
    the crypto market page is backed by CryptoProviderGateway (Binance/OKX/Bybit)
    and must report the same source-of-truth path.
    """
    gateway = CryptoProviderGateway()
    rows = await gateway.health()
    return {
        "order": list(gateway.order),
        "providers": [
            {
                "name": row.get("provider", "unknown"),
                "available": bool(row.get("healthy", False)),
                "status": "healthy" if row.get("healthy", False) else "down",
                "message": (
                    f"universe={row.get('universe', 0)}, quotes={row.get('quotes', 0)}"
                    if row.get("healthy", False)
                    else str(row.get("error", "provider unavailable"))
                ),
            }
            for row in rows
        ],
    }

@router.get("/markets/coverage")
async def market_coverage():
    return await coverage.snapshot()


@router.get("/markets/data-status")
async def market_data_status():
    return data_status.snapshot()


@router.get("/markets/{symbol}")
async def market(symbol: str):
    raw = symbol.upper().replace("/", "")
    try:
        crypto_rows = await _crypto_gateway.market_rows()
    except Exception:
        crypto_rows = []
    found = next((x for x in crypto_rows if str(x.get("symbol", "")).upper().replace("/", "") == raw), None)
    if found:
        return {"analysis_only": True, **found}

    items = await universe.all()
    found_item = next((x for x in items if x.symbol.upper().replace("/", "") == raw or x.symbol.upper() == symbol.upper()), None)
    if not found_item:
        raise HTTPException(404, "instrument not found in current live/configured universe")
    return {
        "analysis_only": True,
        "symbol": found_item.symbol,
        "name": found_item.name,
        "market": found_item.market,
        "asset_type": found_item.asset_type,
        "venue": found_item.venue,
        "currency": found_item.currency,
        "metadata": found_item.metadata or {},
        "quote_status": "provider_unavailable",
    }
