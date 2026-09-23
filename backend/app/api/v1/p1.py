from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from app.main import portfolio_risk_engine, alert_engine, market_provider_registry
from app.portfolio.risk import PositionRisk

router=APIRouter(tags=['p1'])

class Position(BaseModel):
    symbol:str; notional:float; pnl:float=0
class PortfolioRiskRequest(BaseModel):
    equity:float=Field(gt=0); positions:list[Position]=[]; peak_equity:float|None=None
class AlertCreate(BaseModel):
    symbol:str; kind:str; operator:Literal['gt','gte','lt','lte','eq']; threshold:float

@router.post('/portfolio/risk')
def portfolio_risk(body:PortfolioRiskRequest):
    r=portfolio_risk_engine.evaluate(body.equity,[PositionRisk(**p.model_dump()) for p in body.positions],body.peak_equity)
    return {'risk':r.__dict__ if hasattr(r,'__dict__') else {'equity':r.equity,'gross_exposure':r.gross_exposure,'net_exposure':r.net_exposure,'concentration':r.concentration,'drawdown':r.drawdown,'risk_level':r.risk_level,'warnings':r.warnings}}

@router.get('/providers/health')
async def provider_health(): return [x.__dict__ for x in await market_provider_registry.health()]

@router.post('/alerts')
def create_alert(body:AlertCreate):
    n=alert_engine.add(body.symbol,body.kind,body.operator,body.threshold)
    return {'id':n.id,'symbol':n.symbol,'kind':n.kind,'operator':n.operator,'threshold':n.threshold,'enabled':n.enabled}

@router.get('/alerts')
def list_alerts():
    return [{'id':n.id,'symbol':n.symbol,'kind':n.kind,'operator':n.operator,'threshold':n.threshold,'enabled':n.enabled} for n in alert_engine.list()]
