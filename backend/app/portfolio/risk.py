from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class PositionRisk:
    symbol: str; notional: float; weight: float = 0.0; pnl: float = 0.0

@dataclass(slots=True)
class PortfolioRisk:
    equity: float; gross_exposure: float; net_exposure: float; concentration: float
    drawdown: float; risk_level: str; warnings: list[str]

class PortfolioRiskEngine:
    def evaluate(self, equity: float, positions: list[PositionRisk], peak_equity: float | None = None) -> PortfolioRisk:
        equity=max(float(equity),0.0); gross=sum(abs(p.notional) for p in positions); net=sum(p.notional for p in positions)
        weights=[abs(p.notional)/gross for p in positions] if gross else []
        concentration=max(weights, default=0.0)
        peak=max(equity, float(peak_equity or equity)); drawdown=0 if peak==0 else max(0.0,(peak-equity)/peak)
        warnings=[]
        if equity and gross/equity>2: warnings.append('gross exposure exceeds 2x equity')
        if concentration>.5: warnings.append('single-position concentration exceeds 50%')
        if drawdown>.1: warnings.append('drawdown exceeds 10%')
        level='high' if warnings or drawdown>.08 else ('medium' if drawdown>.04 or concentration>.35 else 'low')
        return PortfolioRisk(equity,gross,net,concentration,drawdown,level,warnings)
