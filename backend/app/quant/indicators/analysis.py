"""Human-readable multi-indicator market analysis."""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field
from app.quant.indicators.basic import (
    adl, adx, atr, bollinger, cci, cmf, dmi, donchian, ema, keltner, latest,
    macd, mfi, obv, parabolic_sar, rsi, sma, stochastic, stoch_rsi,
    ultimate_oscillator, vwap, williams_r, roc,
)

class OscillatorState(BaseModel):
    name:str; value:float|None; state:Literal["oversold","overbought","neutral","unknown"]="unknown"; signal:Literal["long","short","none"]="none"; note:str=""
class StructureReport(BaseModel):
    state:str="unknown"; note:str=""; swing_high:float|None=None; swing_low:float|None=None; support:list[float]=Field(default_factory=list); resistance:list[float]=Field(default_factory=list)
class IndicatorReport(BaseModel):
    instrument_id:str; symbol:str; market:str="crypto"; timeframe:str; bars:int; last_price:float|None; last_close_time:int|None
    sma_20:float|None=None; sma_50:float|None=None; sma_200:float|None=None; ema_12:float|None=None; ema_26:float|None=None
    rsi_14:float|None=None; stoch_k:float|None=None; stoch_d:float|None=None; stoch_rsi:float|None=None; cci_20:float|None=None; williams_r:float|None=None; ultimate_osc:float|None=None
    macd:float|None=None; macd_signal:float|None=None; macd_hist:float|None=None; atr_14:float|None=None; adx_14:float|None=None; dmi_plus:float|None=None; dmi_minus:float|None=None
    bb_mid:float|None=None; bb_upper:float|None=None; bb_lower:float|None=None; bb_pct:float|None=None; keltner_mid:float|None=None; keltner_upper:float|None=None; keltner_lower:float|None=None
    vwap:float|None=None; obv:float|None=None; mfi_14:float|None=None; cmf_20:float|None=None; adl:float|None=None; roc_12:float|None=None; psar:float|None=None; donchian_high:float|None=None; donchian_mid:float|None=None; donchian_low:float|None=None
    volume_sma_20:float|None=None; volume_ratio:float|None=None
    trend_sma:Literal["bullish","bearish","neutral","unknown"]="unknown"; trend_label:str="未知"; trend_strength:str="未知"
    price_vs_bb:str="unknown"; oscillators:list[OscillatorState]=Field(default_factory=list); active_signals:list[dict[str,Any]]=Field(default_factory=list)
    structure:StructureReport=Field(default_factory=StructureReport); divergence:str="无明显背离"; overbought_count:int=0; oversold_count:int=0; overbought_score:float=0; oversold_score:float=0
    summary:str=""; narrative:str=""; realtime_note:str=""; data_quality:str="ok"

def _last(s): return latest(s)
def _state(value, low, high, name):
    if value is None:return "unknown","none",f"{name}暂无足够数据"
    if value<low:return "oversold","long",f"{name}={value:.2f}，进入超卖区，说明短线下跌速度较快，但单独不能确认反转。"
    if value>high:return "overbought","short",f"{name}={value:.2f}，进入超买区，说明短线上涨速度较快，但强趋势中可持续高位。"
    return "neutral","none",f"{name}={value:.2f}，处于中性区。"

def _divergence(closes, rsi_s):
    if len(closes)<40:return "无明显背离"
    # Compare the last two local lows/highs in a simple, deterministic way.
    peaks=[]; troughs=[]
    for i in range(2,len(closes)-2):
        if closes[i]>closes[i-1] and closes[i]>=closes[i+1]: peaks.append(i)
        if closes[i]<closes[i-1] and closes[i]<=closes[i+1]: troughs.append(i)
    if len(peaks)>=2 and rsi_s[peaks[-1]] is not None and rsi_s[peaks[-2]] is not None and closes[peaks[-1]]>closes[peaks[-2]] and rsi_s[peaks[-1]]<rsi_s[peaks[-2]]: return "顶背离候选：价格创新高而RSI未同步创新高"
    if len(troughs)>=2 and rsi_s[troughs[-1]] is not None and rsi_s[troughs[-2]] is not None and closes[troughs[-1]]<closes[troughs[-2]] and rsi_s[troughs[-1]]>rsi_s[troughs[-2]]: return "底背离候选：价格创新低而RSI未同步创新低"
    return "无明显背离"

def analyze_bars(*,instrument_id,symbol,timeframe,bars,market="crypto",rsi_period=14,rsi_os=30.0,rsi_ob=70.0):
    if not bars: raise ValueError("empty bars")
    c=[float(x["close"]) for x in bars]; h=[float(x.get("high",x["close"])) for x in bars]; l=[float(x.get("low",x["close"])) for x in bars]; v=[float(x.get("volume") or 0) for x in bars]; n=len(c); p=c[-1]
    s20,s50,s200=sma(c,20),sma(c,50),sma(c,200); e12,e26=ema(c,12),ema(c,26); rs=rsi(c,rsi_period); ml,ms,mh=macd(c); bm,bu,bl=bollinger(c,20); vs=sma(v,20)
    sk,sd=stochastic(h,l,c); sr,_,_=stoch_rsi(c); cc=cci(h,l,c); wr=williams_r(h,l,c); uo=ultimate_oscillator(h,l,c); a=atr(h,l,c); ax=adx(h,l,c); dp,dm=dmi(h,l,c); vw=vwap(h,l,c,v); ob=obv(c,v); mf=mfi(h,l,c,v); cf=cmf(h,l,c,v); ad=adl(h,l,c,v); ro=roc(c); ps=parabolic_sar(h,l); dh,dd,dl=donchian(h,l); km,ku,kl=keltner(h,l,c)
    vals={k:_last(x) for k,x in locals().items() if k in []}
    L=lambda x: _last(x)
    x={"sma20":L(s20),"sma50":L(s50),"sma200":L(s200),"ema12":L(e12),"ema26":L(e26),"rsi":L(rs),"sk":L(sk),"sd":L(sd),"sr":L(sr),"cci":L(cc),"wr":L(wr),"uo":L(uo),"macd":L(ml),"ms":L(ms),"mh":L(mh),"bm":L(bm),"bu":L(bu),"bl":L(bl),"vs":L(vs),"atr":L(a),"adx":L(ax),"dp":L(dp),"dm":L(dm),"vwap":L(vw),"obv":L(ob),"mfi":L(mf),"cmf":L(cf),"adl":L(ad),"roc":L(ro),"psar":L(ps),"dh":L(dh),"dd":L(dd),"dl":L(dl),"km":L(km),"ku":L(ku),"kl":L(kl)}
    bb_pct=(p-x["bl"])/(x["bu"]-x["bl"]) if x["bl"] is not None and x["bu"] is not None and x["bu"]!=x["bl"] else None
    vr=v[-1]/x["vs"] if x["vs"] else None
    trend="unknown"
    if x["sma20"] is not None and x["sma50"] is not None: trend="bullish" if p>x["sma20"]>x["sma50"] else "bearish" if p<x["sma20"]<x["sma50"] else "neutral"
    strength="未知"
    if x["adx"] is not None: strength="强趋势" if x["adx"]>=30 else "中等趋势" if x["adx"]>=20 else "弱趋势/震荡"
    os=[]; obb=[]
    for name,val,lo,hi in [("RSI",x["rsi"],30,70),("Stochastic",x["sk"],20,80),("Stoch RSI",x["sr"],20,80),("CCI",x["cci"],-100,100),("Williams %R",x["wr"],-80,-20),("Ultimate Oscillator",x["uo"],30,70),("MFI",x["mfi"],20,80)]:
        if val is None: continue
        if name=="CCI": state="oversold" if val<-100 else "overbought" if val>100 else "neutral"
        elif name=="Williams %R": state="oversold" if val<-80 else "overbought" if val>-20 else "neutral"
        else: state="oversold" if val<lo else "overbought" if val>hi else "neutral"
        if state=="oversold": os.append(name)
        elif state=="overbought": obb.append(name)
    osc=[]
    for name,val,lo,hi in [("RSI",x["rsi"],30,70),("Stochastic",x["sk"],20,80),("Stoch RSI",x["sr"],20,80),("CCI",x["cci"],-100,100),("Williams %R",x["wr"],-80,-20),("MFI",x["mfi"],20,80)]:
        if val is None: continue
        st,sig,note=_state(val,lo,hi,name) if name not in ("CCI","Williams %R") else (("oversold","long",f"{name}={val:.2f}，进入超卖区。") if ((name=="CCI" and val<-100) or (name=="Williams %R" and val<-80)) else ("overbought","short",f"{name}={val:.2f}，进入超买区。") if ((name=="CCI" and val>100) or (name=="Williams %R" and val>-20)) else ("neutral","none",f"{name}={val:.2f}，中性。"))
        osc.append(OscillatorState(name=name,value=round(val,4),state=st,signal=sig,note=note))
    if bb_pct is not None: osc.append(OscillatorState(name="Bollinger",value=round(bb_pct,4),state="oversold" if bb_pct<0.05 else "overbought" if bb_pct>0.95 else "neutral",signal="long" if bb_pct<0.05 else "short" if bb_pct>0.95 else "none",note="价格靠近下轨/上轨，需结合趋势判断。"))
    if x["mh"] is not None: osc.append(OscillatorState(name="MACD",value=round(x["mh"],6),signal="long" if x["mh"]>0 else "short",note="MACD柱为正表示动能偏多；为负表示动能偏空。"))
    if x["adx"] is not None: osc.append(OscillatorState(name="ADX",value=round(x["adx"],3),note="ADX衡量趋势强度，不决定涨跌方向。"))
    swing_hi=max(h[-20:]); swing_lo=min(l[-20:]); support=sorted({round(swing_lo,6),*(round(z,6) for z in [x["bl"],x["dl"],x["km"]] if z is not None and z<p)})[-3:]; resistance=sorted({round(swing_hi,6),*(round(z,6) for z in [x["bu"],x["dh"],x["ku"]] if z is not None and z>p)})[:3]
    structure="上升结构" if len(c)>=10 and c[-1]>c[-5] and min(l[-5:])>min(l[-10:-5]) else "下降结构" if len(c)>=10 and c[-1]<c[-5] and max(h[-5:])<max(h[-10:-5]) else "震荡结构"
    structure_note={"上升结构":"近期高低点整体抬高，回踩支撑后需观察是否继续创出新高。","下降结构":"近期高低点整体降低，反弹能否突破前高是关键。","震荡结构":"高低点尚未形成连续单边结构，重点观察区间突破和回踩。"}[structure]
    div=_divergence(c,rs)
    signals=[]
    if x["mh"] is not None:
        # Strength is derived from the observed MACD histogram relative to ATR,
        # never from a fixed confidence constant. It is a signal intensity, not
        # a probability and is deliberately capped for UI readability.
        atr_value = x["atr"]
        if atr_value is not None and atr_value > 0:
            macd_intensity = abs(x["mh"]) / atr_value
            macd_strength = max(0.0, min(1.0, macd_intensity))
        else:
            macd_strength = None
        signals.append({"name":"macd","direction":"long" if x["mh"]>0 else "short","strength":round(macd_strength,4) if macd_strength is not None else None,"value":x["mh"],"strength_basis":"abs(macd_hist)/atr" if macd_strength is not None else "insufficient_volatility_data"})
    if vr is not None and vr>=2: signals.append({"name":"volume_spike","direction":"neutral","strength":min(1,vr/4),"value":vr,"strength_basis":"volume_ratio/4"})
    narrative=f"{timeframe}当前为{('上涨' if trend=='bullish' else '下跌' if trend=='bearish' else '震荡/混合')}，趋势强度{strength}。"
    if obb: narrative+=f" {', '.join(obb)}出现超买，说明短线偏热；这不是单独做空确认。"
    if os: narrative+=f" {', '.join(os)}出现超卖，说明短线偏冷；这不是单独做多确认。"
    if div!="无明显背离": narrative+=f" {div}。"
    if trend=="bullish" and x["mh"] is not None and x["mh"]<0: narrative+=" 价格趋势仍偏多，但MACD动能出现反向变化，需要防范上涨动能衰减。"
    if trend=="bearish" and x["mh"] is not None and x["mh"]>0: narrative+=" 价格趋势仍偏空，但MACD动能修复，可能出现反弹。"
    summary=f"{timeframe}：趋势{('上涨' if trend=='bullish' else '下跌' if trend=='bearish' else '震荡')}；趋势强度{strength}；超买{len(obb)}项；超卖{len(os)}项；结构{structure}。"
    return IndicatorReport(instrument_id=instrument_id,symbol=symbol,market=market,timeframe=timeframe,bars=n,last_price=p,last_close_time=int(bars[-1].get("close_time") or 0),sma_20=x["sma20"],sma_50=x["sma50"],sma_200=x["sma200"],ema_12=x["ema12"],ema_26=x["ema26"],rsi_14=x["rsi"],stoch_k=x["sk"],stoch_d=x["sd"],stoch_rsi=x["sr"],cci_20=x["cci"],williams_r=x["wr"],ultimate_osc=x["uo"],macd=x["macd"],macd_signal=x["ms"],macd_hist=x["mh"],atr_14=x["atr"],adx_14=x["adx"],dmi_plus=x["dp"],dmi_minus=x["dm"],bb_mid=x["bm"],bb_upper=x["bu"],bb_lower=x["bl"],bb_pct=bb_pct,keltner_mid=x["km"],keltner_upper=x["ku"],keltner_lower=x["kl"],vwap=x["vwap"],obv=x["obv"],mfi_14=x["mfi"],cmf_20=x["cmf"],adl=x["adl"],roc_12=x["roc"],psar=x["psar"],donchian_high=x["dh"],donchian_mid=x["dd"],donchian_low=x["dl"],volume_sma_20=x["vs"],volume_ratio=vr,trend_sma=trend,trend_label={"bullish":"上涨","bearish":"下跌","neutral":"震荡/混合","unknown":"未知"}[trend],trend_strength=strength,price_vs_bb="below_lower" if bb_pct is not None and bb_pct<0 else "above_upper" if bb_pct is not None and bb_pct>1 else "lower_half" if bb_pct is not None and bb_pct<.5 else "upper_half" if bb_pct is not None else "unknown",oscillators=osc,active_signals=signals,structure=StructureReport(state=structure,note=structure_note,swing_high=swing_hi,swing_low=swing_lo,support=support,resistance=resistance),divergence=div,overbought_count=len(obb),oversold_count=len(os),overbought_score=min(1,len(obb)/5),oversold_score=min(1,len(os)/5),summary=summary,narrative=narrative,realtime_note="当前周期数据包含最新行情；未收盘K线的指标属于临时值，突破/反转需等待本周期收盘确认。",data_quality="ok")
