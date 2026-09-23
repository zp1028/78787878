from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.ai.orchestrator.engine import AIOrchestrator
from app.risk.engine import RiskEngine
from app.core.config import settings
from app.core.event_bus import EventBus
from app.db.session import init_db
from app.models.instrument import InstrumentRegistry
from app.providers.crypto.gateway import CryptoWsGateway
from app.services.crypto_provider_gateway import CryptoProviderGateway
from app.providers.registry import ProviderRegistry
from app.quant.attention.engine import AttentionEngine
from app.quant.features.engine import FeatureEngine
from app.quant.observation.engine import ObservationEngine
from app.quant.signals.engine import SignalEngine
from app.repositories.instrument_repo import load_all_into_registry, upsert_instrument
from app.repositories.candle_repo import CandleRecoveryService
from app.repositories.quant_repo import QuantRepository
from app.portfolio.risk import PortfolioRiskEngine
from app.alerts.engine import AlertEngine
from app.providers.market.registry import MarketProviderRegistry

bus = EventBus()
instruments = InstrumentRegistry()
registry = ProviderRegistry()
crypto_ws = CryptoWsGateway(settings, bus, instruments)
crypto_market_gateway = CryptoProviderGateway()
quant_repo = QuantRepository()
feature_engine = FeatureEngine(bus, repository=quant_repo)
signal_engine = SignalEngine(bus, feature_engine, repository=quant_repo)

candle_recovery = CandleRecoveryService(
    bus, instruments, settings.symbols, ["1m", "5m", "15m", "1h", "4h", "1d"], crypto_gateway=crypto_market_gateway
)

attention_engine = AttentionEngine(bus)
observation_engine = ObservationEngine(bus)
risk_engine = RiskEngine(bus)

portfolio_risk_engine = PortfolioRiskEngine()
alert_engine = AlertEngine()
market_provider_registry = MarketProviderRegistry()

ai_orchestrator = AIOrchestrator(
    bus,
    feature_engine,
    signal_engine,
    attention_engine,
    auto_on_attention=True,
    attention_threshold=0.55,
    auto_on_observation=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        loaded = load_all_into_registry(instruments)
        print(f"[startup] database ready, loaded {loaded} instruments")
    except Exception as exc:
        print(f"[startup] database init skipped/failed: {exc}")

    feature_engine.subscribe()
    signal_engine.subscribe()
    attention_engine.subscribe()
    observation_engine.subscribe()
    ai_orchestrator.subscribe()
    candle_recovery.subscribe()

    registry.register("crypto-ws", crypto_ws)
    await crypto_ws.start()
    # REST bootstrap makes the local candle cache usable immediately, even
    # after a cold start or a period where the websocket was disconnected.
    await candle_recovery.bootstrap(limit=300)

    # Background prewarm: prime the crypto market-row cache and the hot kline
    # cache so first page loads are fast instead of paying a cold 3-8s fetch.
    async def _prewarm() -> None:
        try:
            from app.api.v1 import markets as _markets

            rows = await _markets._crypto_gateway.market_rows()
            print(f"[prewarm] crypto market rows cached: {len(rows)}")
        except Exception as exc:
            print(f"[prewarm] market rows skipped: {exc}")
        try:
            from app.data.klines import fetch_binance_klines

            for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"):
                await fetch_binance_klines(sym, "15m", 300)
                await fetch_binance_klines(sym, "1h", 300)
            print("[prewarm] hot klines cached")
        except Exception as exc:
            print(f"[prewarm] klines skipped: {exc}")

    import asyncio as _asyncio

    _asyncio.create_task(_prewarm())

    try:
        for inst in instruments.list_all():
            upsert_instrument(inst)
    except Exception as exc:
        print(f"[startup] instrument persist skipped: {exc}")

    yield
    await crypto_ws.stop()


from app.api.v1.analysis import router as analysis_router
from app.api.v1.advice import router as advice_router
from app.api.v1.indicators import router as indicators_router
from app.api.v1.markets import router as markets_router
from app.api.v1.candles import router as candles_router
from app.api.v1.observations import router as observations_router
from app.api.v1.strategies import router as strategies_router
from app.api.v1.websocket import router as ws_router
from app.api.v1.report import router as report_router
from app.api.v1.unified_report import router as unified_report_router
from app.api.v1 import fundamentals
from app.api.v1.us_fundamentals import router as us_fundamentals_router
from app.api.v1.hk_data import router as hk_data_router
from app.api.v1.reports import router as reports_router
from app.api.v1.instrument_snapshot import router as instrument_snapshot_router
from app.api.v1.derivatives import router as derivatives_router
from app.api.v1.market_capabilities import router as market_capabilities_router
from app.api.v1.us_valuation import router as us_valuation_router
from app.api.v1.crypto_aggregation import router as crypto_aggregation_router
from app.api.v1.instrument_analysis_snapshot import router as instrument_analysis_snapshot_router
from app.api.v1.mtf import router as mtf_router
from app.api.v1.analysis_feed import router as analysis_feed_router
from app.api.v1.terminal import router as terminal_router
from app.api.v1.terminal_analysis import router as terminal_analysis_router
from app.api.v1.structure import router as structure_router
from app.api.v1.scenarios import router as scenarios_router
from app.api.v1.risk_map import router as risk_map_router
from app.api.v1.p26 import router as p26_router
from app.api.v1.p1 import router as p1_router

app = FastAPI(title="Smart Trader API", version="1.7.1", lifespan=lifespan)
app.include_router(markets_router, prefix="/api/v1")
app.include_router(candles_router, prefix="/api/v1")
app.include_router(observations_router, prefix="/api/v1")
app.include_router(strategies_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(advice_router, prefix="/api/v1")
app.include_router(indicators_router, prefix="/api/v1")
app.include_router(report_router, prefix="/api/v1")
app.include_router(unified_report_router, prefix="/api/v1")
app.include_router(fundamentals.router, prefix="/api/v1")
app.include_router(us_fundamentals_router, prefix="/api/v1")
app.include_router(hk_data_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(instrument_snapshot_router, prefix="/api/v1")
app.include_router(derivatives_router, prefix="/api/v1")
app.include_router(market_capabilities_router, prefix="/api/v1")
app.include_router(us_valuation_router, prefix="/api/v1")
app.include_router(crypto_aggregation_router, prefix="/api/v1")
app.include_router(instrument_analysis_snapshot_router, prefix="/api/v1")
app.include_router(mtf_router, prefix="/api/v1")
app.include_router(analysis_feed_router, prefix="/api/v1")
app.include_router(terminal_router, prefix="/api/v1")
app.include_router(terminal_analysis_router, prefix="/api/v1")
app.include_router(structure_router, prefix="/api/v1")
app.include_router(scenarios_router, prefix="/api/v1")
app.include_router(risk_map_router, prefix="/api/v1")
app.include_router(p26_router, prefix="/api/v1")
app.include_router(p1_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")

# CORS — the web client may be served from a different origin in dev mode.
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/runtime/status")
async def runtime_status():
    """Return deployment/runtime identity without fabricating market health.

    Provider availability remains sourced from /api/v1/markets/providers/health;
    this endpoint only identifies the backend instance and the configured crypto
    gateway order so Android can distinguish a reachable backend from a stale or
    misrouted endpoint.
    """
    return {
        "status": "ok",
        "version": app.version,
        "server_time_ms": int(__import__("time").time() * 1000),
        "crypto_gateway": {
            "providers": list(crypto_market_gateway.order),
            "source": "CryptoProviderGateway",
            "market_endpoint": "/api/v1/markets?market=crypto",
            "provider_health_endpoint": "/api/v1/markets/providers/health",
        },
    }


@app.get("/api/v1/runtime/ready")
async def runtime_ready():
    """Deployment readiness: backend is serving at least one live crypto quote."""
    try:
        rows = await crypto_market_gateway.market_rows()
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={
            "status": "not_ready",
            "reason": "no_live_crypto_market",
            "error": str(exc),
        }) from exc
    live = [r for r in rows if r.get("quote_status") == "live" and r.get("price") is not None]
    if not live:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"status": "not_ready", "reason": "no_live_crypto_market"})
    return {
        "status": "ready",
        "market": "crypto",
        "live_market_count": len(live),
        "sample": [{"symbol": r.get("symbol"), "provider": r.get("provider")} for r in live[:5]],
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": app.version,
        "provider": crypto_ws.health.model_dump(),
        "providers": crypto_ws.health_snapshot(),
        "symbols": sorted(crypto_ws.subscriptions),
        "instruments": [i.model_dump() for i in instruments.list_all()],
        "database_url_scheme": settings.database_url.split("://")[0],
        "quant": {
            "feature_engine": True,
            "signal_engine": True,
            "attention_engine": True,
            "observation_engine": True,
            "ai_orchestrator": True,
            "research_backtest_internal": True,
            "risk_engine": True,
            "analysis_only": True,
            "analytical_scenarios": True,
            "indicators_mtf": True,
            "attention_top": [
                {"symbol": e.symbol, "score": e.score, "regime": e.regime}
                for e in attention_engine.ranking(5)
            ],
            "observation_count": len(observation_engine.list_all()),
            "public_portfolio_account_api": False,
            "multi_agent": True,
            "market_regime": True,
            "provider_registry": True,
            "execution_api": False,
            "account_api": False,
            "order_api": False,
        },
    }


# Serve the built web frontend (single-port deployment) when present.
# Catch-all added last so every /api route above wins over the SPA fallback.
import os

from fastapi import HTTPException
from fastapi.responses import FileResponse

_STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="api route not found")
    candidate = os.path.join(_STATIC_DIR, full_path)
    if full_path and os.path.isfile(candidate):
        # Hashed assets (js/css) may be cached; plain files are revalidated.
        ext = os.path.splitext(full_path)[1].lower()
        headers = {}
        if ext not in {".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".woff2", ".woff", ".ico"}:
            headers["Cache-Control"] = "no-cache"
        return FileResponse(candidate, headers=headers)
    index = os.path.join(_STATIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="not found")
