from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class AgentFinding:
    agent: str; stance: str; score: float; confidence: float; reasons: list[str]

def analyze_money_flow(features):
    has_vr = features.get('volume_ratio') is not None
    has_obv = features.get('obv_slope') is not None
    vr=float(features.get('volume_ratio') or 1)
    obv=float(features.get('obv_slope') or 0)
    score=max(0,min(1,.5 + .15*(vr-1) + .2*(1 if obv>0 else -1)))
    confidence=(int(has_vr)+int(has_obv))/2
    return AgentFinding('MoneyFlowAgent','bullish' if score>.55 else 'bearish' if score<.45 else 'neutral',score,confidence,['volume ratio and OBV slope'])

def analyze_sentiment(features):
    value=features.get('sentiment_score'); score=.5 if value is None else max(0,min(1,(float(value)+1)/2))
    confidence=0.0 if value is None else 1.0
    return AgentFinding('SentimentAgent','bullish' if score>.55 else 'bearish' if score<.45 else 'neutral',score,confidence,['point-in-time sentiment input availability'])

def debate(technical: AgentFinding, money: AgentFinding, sentiment: AgentFinding):
    score=(technical.score*.5+money.score*.3+sentiment.score*.2)
    stance='bullish' if score>.58 else 'bearish' if score<.42 else 'neutral'
    return AgentFinding('DebateEngine',stance,score,round((technical.confidence+money.confidence+sentiment.confidence)/3,3),['weighted independent agent findings'])
