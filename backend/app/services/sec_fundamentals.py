from __future__ import annotations
import json
import urllib.request
from typing import Any

SEC_BASE = "https://data.sec.gov"

class SecFundamentalsService:
    """Read-only SEC discovery/XBRL adapter. No trading or account access."""
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    def _get_json(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(
            SEC_BASE + path,
            headers={"User-Agent": "SmartTrader/1.0 personal research contact=research@example.com", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def company_facts(self, cik: str) -> dict[str, Any]:
        digits = str(cik).strip().upper().replace("CIK", "")
        if not digits.isdigit():
            raise ValueError("invalid CIK")
        return self._get_json(f"/api/xbrl/companyfacts/CIK{int(digits):010d}.json")

    def latest(self, cik: str) -> dict[str, Any]:
        raw = self.company_facts(cik)
        facts = raw.get("facts", {})
        usgaap = facts.get("us-gaap", {})
        wanted = {
            "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
            "net_income": ("NetIncomeLoss",),
            "assets": ("Assets",),
            "liabilities": ("Liabilities",),
            "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
            "cash": ("CashAndCashEquivalentsAtCarryingValue",),
            "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
        }
        out: dict[str, Any] = {"cik": f"{int(str(cik).replace('CIK','')):010d}", "company": raw.get("entityName"), "facts": {}}
        for label, tags in wanted.items():
            fact = next((usgaap.get(tag) for tag in tags if usgaap.get(tag)), None)
            if not fact:
                continue
            units = fact.get("units", {})
            series = next(iter(units.values()), [])
            if not series:
                continue
            latest = sorted(series, key=lambda x: (x.get("filed", ""), x.get("end", "")))[-1]
            out["facts"][label] = {"value": latest.get("val"), "unit": latest.get("unit"), "end": latest.get("end"), "filed": latest.get("filed"), "form": latest.get("form")}
        return out
