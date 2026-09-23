from __future__ import annotations
from dataclasses import dataclass, field
from uuid import uuid4

@dataclass(slots=True)
class ObservationNode:
    id: str; symbol: str; kind: str; operator: str; threshold: float; enabled: bool=True
    last_triggered: float | None=None; metadata: dict = field(default_factory=dict)

class AlertEngine:
    def __init__(self): self.nodes: dict[str, ObservationNode]={}
    def add(self, symbol, kind, operator, threshold, metadata=None):
        n=ObservationNode(str(uuid4()),symbol,kind,operator,float(threshold),True,metadata=metadata or {}); self.nodes[n.id]=n; return n
    def evaluate(self, symbol: str, kind: str, value: float):
        hits=[]
        for n in self.nodes.values():
            if not n.enabled or n.symbol!=symbol or n.kind!=kind: continue
            ok={'gt':value>n.threshold,'gte':value>=n.threshold,'lt':value<n.threshold,'lte':value<=n.threshold,'eq':value==n.threshold}.get(n.operator,False)
            if ok and n.last_triggered != value: n.last_triggered=value; hits.append(n)
        return hits
    def list(self): return list(self.nodes.values())
