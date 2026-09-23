from __future__ import annotations
from .models import AccountSnapshot, ReconciliationResult

def reconcile(local: AccountSnapshot, remote: AccountSnapshot) -> ReconciliationResult:
    lm={p.symbol:p for p in local.positions}; rm={p.symbol:p for p in remote.positions}
    missing_local=sorted(set(rm)-set(lm)); missing_remote=sorted(set(lm)-set(rm)); mismatched=[]
    for symbol in sorted(set(lm)&set(rm)):
        a,b=lm[symbol],rm[symbol]
        if abs(a.quantity-b.quantity)>1e-9 or abs(a.mark_price-b.mark_price)>max(1e-9,abs(b.mark_price)*1e-6):
            mismatched.append(symbol)
    return ReconciliationResult(matched=not missing_local and not missing_remote and not mismatched, missing_local=missing_local, missing_remote=missing_remote, mismatched=mismatched)
