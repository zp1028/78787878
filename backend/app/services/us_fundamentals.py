from __future__ import annotations

import json
import math
import urllib.request
from datetime import datetime, timezone
from typing import Any

SEC_BASE = "https://data.sec.gov"

class UsFundamentalsService:
    """Read-only US equity fundamentals adapter backed by SEC public XBRL APIs."""
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self._ticker_cache: dict[str, dict[str, Any]] | None = None

    def _get_json(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(
            SEC_BASE + path,
            headers={
                "User-Agent": "SmartTrader/1.1 personal-research contact=research@example.com",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def ticker_map(self) -> dict[str, dict[str, Any]]:
        if self._ticker_cache is None:
            raw = self._get_json("/files/company_tickers.json")
            self._ticker_cache = {
                str(v.get("ticker", "")).upper(): {
                    "cik": str(v.get("cik_str", "")),
                    "name": v.get("title"),
                }
                for v in raw.values()
                if v.get("ticker") and v.get("cik_str")
            }
        return self._ticker_cache

    def resolve(self, ticker: str) -> dict[str, Any]:
        key = ticker.strip().upper()
        item = self.ticker_map().get(key)
        if not item:
            raise ValueError(f"unknown SEC ticker: {ticker}")
        return {"ticker": key, **item}

    def company_facts(self, cik: str) -> dict[str, Any]:
        digits = str(cik).strip().upper().replace("CIK", "")
        if not digits.isdigit():
            raise ValueError("invalid CIK")
        return self._get_json(f"/api/xbrl/companyfacts/CIK{int(digits):010d}.json")

    @staticmethod
    def _series(fact: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not fact:
            return []
        units = fact.get("units", {})
        # Prefer USD / USD-per-share, then the first available unit.
        for unit in ("USD", "USD/shares", "USD-per-shares", "shares"):
            if unit in units:
                return units[unit]
        return next(iter(units.values()), [])

    @staticmethod
    def _latest(series: list[dict[str, Any]]) -> dict[str, Any] | None:
        valid = [x for x in series if x.get("val") is not None]
        if not valid:
            return None
        return sorted(valid, key=lambda x: (x.get("filed", ""), x.get("end", "")))[-1]

    @staticmethod
    def _periodic(series: list[dict[str, Any]], form: str | None = None) -> list[dict[str, Any]]:
        rows = [x for x in series if x.get("val") is not None]
        if form:
            rows = [x for x in rows if x.get("form") == form]
        return sorted(rows, key=lambda x: (x.get("end", ""), x.get("filed", "")), reverse=True)

    def latest(self, ticker: str) -> dict[str, Any]:
        resolved = self.resolve(ticker)
        raw = self.company_facts(resolved["cik"])
        usgaap = raw.get("facts", {}).get("us-gaap", {})
        wanted = {
            "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
            "gross_profit": ("GrossProfit",),
            "operating_income": ("OperatingIncomeLoss",),
            "net_income": ("NetIncomeLoss",),
            "assets": ("Assets",),
            "liabilities": ("Liabilities",),
            "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
            "cash": ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
            "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
            "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
            "diluted_eps": ("EarningsPerShareDiluted",),
            "basic_eps": ("EarningsPerShareBasic",),
            "shares_diluted": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
        }
        facts: dict[str, Any] = {}
        for label, tags in wanted.items():
            fact = next((usgaap.get(tag) for tag in tags if usgaap.get(tag)), None)
            latest = self._latest(self._series(fact))
            if latest:
                facts[label] = {k: latest.get(k) for k in ("val", "unit", "start", "end", "filed", "form")}

        def val(name: str) -> float | None:
            v = facts.get(name, {}).get("val")
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        revenue, gross, op, net, equity, ocf, capex = [val(x) for x in ("revenue", "gross_profit", "operating_income", "net_income", "equity", "operating_cash_flow", "capex")]
        derived: dict[str, Any] = {
            "gross_margin": _ratio(gross, revenue),
            "operating_margin": _ratio(op, revenue),
            "net_margin": _ratio(net, revenue),
            "roe": _ratio(net, equity),
            "free_cash_flow": (ocf - capex) if ocf is not None and capex is not None else None,
        }
        freshness = max((x.get("filed", "") for x in facts.values()), default=None)
        return {
            "ticker": resolved["ticker"],
            "cik": f"{int(resolved['cik']):010d}",
            "company": raw.get("entityName") or resolved.get("name"),
            "source": "SEC XBRL companyfacts",
            "read_only": True,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "latest_filing_date": freshness,
            "facts": facts,
            "derived": derived,
            "availability": {"sec": True, "market_multiples": False, "forward_estimates": False},
            "notes": [
                "SEC facts are filing data, not a real-time quote feed.",
                "PE/PB/PS/EV-EBITDA require a synchronized market-cap/price/enterprise-value provider and are not fabricated here.",
            ],
        }


def _ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b
