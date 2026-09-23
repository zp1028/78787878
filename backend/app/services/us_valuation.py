from __future__ import annotations
from typing import Any
from app.services.us_fundamentals import UsFundamentalsService

class UsValuationService:
    """Derives valuation only when SEC facts and a synchronized quote are both present."""
    def __init__(self, fundamentals: UsFundamentalsService | None = None):
        self.fundamentals = fundamentals or UsFundamentalsService()

    def build(self, ticker: str, price: float | None, quote_time: str | None = None) -> dict[str, Any]:
        base = self.fundamentals.latest(ticker)
        facts = base.get("facts", {})
        def n(key: str):
            try: return float(facts.get(key, {}).get("val"))
            except (TypeError, ValueError): return None
        shares = n("shares_diluted")
        equity = n("equity")
        revenue = n("revenue")
        net = n("net_income")
        assets = n("assets")
        liabilities = n("liabilities")
        cash = n("cash")
        market_cap = price * shares if price is not None and shares else None
        enterprise_value = market_cap + liabilities - cash if market_cap is not None and liabilities is not None and cash is not None else None
        return {
            "ticker": base["ticker"], "price": price, "quote_time": quote_time,
            "market_cap": market_cap,
            "pe": market_cap / net if market_cap is not None and net not in (None, 0) else None,
            "pb": market_cap / equity if market_cap is not None and equity not in (None, 0) else None,
            "ps": market_cap / revenue if market_cap is not None and revenue not in (None, 0) else None,
            "enterprise_value": enterprise_value,
            "ev_to_sales": enterprise_value / revenue if enterprise_value is not None and revenue not in (None, 0) else None,
            "availability": {
                "price": price is not None,
                "shares": shares is not None,
                "market_cap": market_cap is not None,
                "pe": market_cap is not None and net not in (None, 0),
                "pb": market_cap is not None and equity not in (None, 0),
                "ps": market_cap is not None and revenue not in (None, 0),
                "enterprise_value": enterprise_value is not None,
                "ev_to_sales": enterprise_value is not None and revenue not in (None, 0),
            },
            "source": "SEC XBRL + synchronized market quote",
            "analysis_only": True,
        }
