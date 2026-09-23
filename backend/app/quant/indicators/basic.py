"""Pure-Python technical indicators (no numpy required).

All functions operate on list[float] closing (or other) series and return
either a scalar (latest value) or a full series of the same length.
"""

from __future__ import annotations


def sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    window_sum = sum(values[:period])
    out[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out[i] = window_sum / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or not values:
        return out
    k = 2.0 / (period + 1)
    # seed with SMA of first `period` bars when possible
    if len(values) >= period:
        seed = sum(values[:period]) / period
        out[period - 1] = seed
        prev = seed
        start = period
    else:
        prev = values[0]
        out[0] = prev
        start = 1
    for i in range(start, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Returns (macd_line, signal_line, histogram)."""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]  # type: ignore[operator]
    # signal is EMA of macd_line (skip Nones)
    valid = [v for v in macd_line if v is not None]
    if not valid:
        return macd_line, [None] * len(closes), [None] * len(closes)
    # build aligned signal series
    signal_series = ema([v if v is not None else 0.0 for v in macd_line], signal)
    # zero out positions where macd was None
    for i, v in enumerate(macd_line):
        if v is None:
            signal_series[i] = None
    hist: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if macd_line[i] is not None and signal_series[i] is not None:
            hist[i] = macd_line[i] - signal_series[i]  # type: ignore[operator]
    return macd_line, signal_series, hist


def bollinger(
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Returns (mid, upper, lower)."""
    mid = sma(closes, period)
    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mean = mid[i]
        if mean is None:
            continue
        var = sum((x - mean) ** 2 for x in window) / period
        std = var ** 0.5
        upper[i] = mean + num_std * std
        lower[i] = mean - num_std * std
    return mid, upper, lower


def latest(series: list[float | None]) -> float | None:
    for v in reversed(series):
        if v is not None:
            return v
    return None

def true_range(highs, lows, closes):
    out=[None]*len(closes)
    if not closes:return out
    out[0]=highs[0]-lows[0]
    for i in range(1,len(closes)): out[i]=max(highs[i]-lows[i],abs(highs[i]-closes[i-1]),abs(lows[i]-closes[i-1]))
    return out

def atr(highs,lows,closes,period=14):
    return ema([float(x or 0) for x in true_range(highs,lows,closes)],period)

def stochastic(highs,lows,closes,period=14):
    k=[None]*len(closes)
    for i in range(period-1,len(closes)):
        hi=max(highs[i-period+1:i+1]); lo=min(lows[i-period+1:i+1]); k[i]=50.0 if hi==lo else 100*(closes[i]-lo)/(hi-lo)
    d=sma([x or 0 for x in k],3); d=[None if k[i] is None else d[i] for i in range(len(k))]
    return k,d

def roc(closes,period=12):
    out=[None]*len(closes)
    for i in range(period,len(closes)):
        if closes[i-period]: out[i]=(closes[i]-closes[i-period])/closes[i-period]*100
    return out

def obv(closes,volumes):
    out=[None]*len(closes)
    if not closes:return out
    total=0.0; out[0]=total
    for i in range(1,len(closes)):
        if closes[i]>closes[i-1]:total+=volumes[i]
        elif closes[i]<closes[i-1]:total-=volumes[i]
        out[i]=total
    return out

def mfi(highs,lows,closes,volumes,period=14):
    out=[None]*len(closes); tp=[(h+l+c)/3 for h,l,c in zip(highs,lows,closes)]
    for i in range(period,len(closes)):
        pos=neg=0.0
        for j in range(i-period+1,i+1):
            flow=tp[j]*volumes[j]
            if j==0 or tp[j]>=tp[j-1]:pos+=flow
            else:neg+=flow
        out[i]=100.0 if neg==0 else 100-100/(1+pos/neg)
    return out

def cci(highs,lows,closes,period=20):
    out=[None]*len(closes); tp=[(h+l+c)/3 for h,l,c in zip(highs,lows,closes)]
    for i in range(period-1,len(closes)):
        w=tp[i-period+1:i+1]; mean=sum(w)/period; md=sum(abs(x-mean) for x in w)/period; out[i]=0.0 if md==0 else (tp[i]-mean)/(0.015*md)
    return out

def williams_r(highs,lows,closes,period=14):
    out=[None]*len(closes)
    for i in range(period-1,len(closes)):
        hi=max(highs[i-period+1:i+1]); lo=min(lows[i-period+1:i+1]); out[i]=-50 if hi==lo else -100*(hi-closes[i])/(hi-lo)
    return out

def adx(highs,lows,closes,period=14):
    atrs=atr(highs,lows,closes,period); plus=[0.0]*len(closes); minus=[0.0]*len(closes)
    for i in range(1,len(closes)):
        up=highs[i]-highs[i-1]; down=lows[i-1]-lows[i]; plus[i]=up if up>down and up>0 else 0; minus[i]=down if down>up and down>0 else 0
    dx=[None]*len(closes)
    for i,a in enumerate(atrs):
        if a and a>0:
            p=100*plus[i]/a; m=100*minus[i]/a; den=p+m; dx[i]=0 if den==0 else 100*abs(p-m)/den
    return ema([x or 0 for x in dx],period)

def stoch_rsi(closes, period=14, smooth_k=3, smooth_d=3):
    rs = rsi(closes, period)
    raw=[None]*len(closes)
    for i in range(len(closes)):
        if i < period*2 or rs[i] is None: continue
        w=[x for x in rs[i-period+1:i+1] if x is not None]
        if not w: continue
        lo=min(w); hi=max(w); raw[i]=0.0 if hi==lo else (rs[i]-lo)/(hi-lo)*100
    k=sma([x or 0 for x in raw], smooth_k)
    k=[None if raw[i] is None else k[i] for i in range(len(raw))]
    d=sma([x or 0 for x in k], smooth_d)
    d=[None if k[i] is None else d[i] for i in range(len(k))]
    return raw,k,d


def vwap(highs,lows,closes,volumes):
    out=[None]*len(closes); pv=0.0; vv=0.0
    for i,(h,l,c,v) in enumerate(zip(highs,lows,closes,volumes)):
        tp=(h+l+c)/3; pv += tp*v; vv += v; out[i]=pv/vv if vv else None
    return out


def adl(highs,lows,closes,volumes):
    out=[None]*len(closes); total=0.0
    for i,(h,l,c,v) in enumerate(zip(highs,lows,closes,volumes)):
        mfm=0.0 if h==l else ((c-l)-(h-c))/(h-l); total += mfm*v; out[i]=total
    return out


def cmf(highs,lows,closes,volumes,period=20):
    out=[None]*len(closes)
    for i in range(period-1,len(closes)):
        mf=0.0; vol=0.0
        for j in range(i-period+1,i+1):
            h,l,c,v=highs[j],lows[j],closes[j],volumes[j]
            mf += (0.0 if h==l else ((c-l)-(h-c))/(h-l))*v; vol += v
        out[i]=mf/vol if vol else 0.0
    return out


def dmi(highs,lows,closes,period=14):
    tr=true_range(highs,lows,closes)
    plus=[0.0]*len(closes); minus=[0.0]*len(closes)
    for i in range(1,len(closes)):
        up=highs[i]-highs[i-1]; dn=lows[i-1]-lows[i]
        plus[i]=up if up>dn and up>0 else 0.0; minus[i]=dn if dn>up and dn>0 else 0.0
    atrs=ema([float(x or 0) for x in tr],period)
    pdi=[None]*len(closes); mdi=[None]*len(closes)
    for i,a in enumerate(atrs):
        if a and a>0: pdi[i]=100*plus[i]/a; mdi[i]=100*minus[i]/a
    return pdi,mdi


def parabolic_sar(highs,lows,step=0.02,max_step=0.2):
    n=len(highs); out=[None]*n
    if n<2:return out
    bull=True; sar=lows[0]; ep=highs[0]; af=step; out[0]=sar
    for i in range(1,n):
        sar=sar+af*(ep-sar)
        if bull:
            sar=min(sar,lows[i-1],lows[i-2] if i>1 else lows[i-1])
            if lows[i]<sar:
                bull=False; sar=ep; ep=lows[i]; af=step
            elif highs[i]>ep:
                ep=highs[i]; af=min(max_step,af+step)
        else:
            sar=max(sar,highs[i-1],highs[i-2] if i>1 else highs[i-1])
            if highs[i]>sar:
                bull=True; sar=ep; ep=highs[i]; af=step
            elif lows[i]<ep:
                ep=lows[i]; af=min(max_step,af+step)
        out[i]=sar
    return out


def donchian(highs,lows,period=20):
    hi=[None]*len(highs); lo=[None]*len(lows); mid=[None]*len(lows)
    for i in range(period-1,len(highs)):
        hi[i]=max(highs[i-period+1:i+1]); lo[i]=min(lows[i-period+1:i+1]); mid[i]=(hi[i]+lo[i])/2
    return hi,mid,lo


def keltner(highs,lows,closes,ema_period=20,atr_period=10,mult=2.0):
    mid=ema(closes,ema_period); a=atr(highs,lows,closes,atr_period)
    up=[None]*len(closes); lo=[None]*len(closes)
    for i in range(len(closes)):
        if mid[i] is not None and a[i] is not None: up[i]=mid[i]+mult*a[i]; lo[i]=mid[i]-mult*a[i]
    return mid,up,lo


def ultimate_oscillator(highs,lows,closes,short=7,medium=14,long=28):
    out=[None]*len(closes); bp=[0.0]*len(closes); tr=[0.0]*len(closes)
    for i in range(len(closes)):
        prev=closes[i-1] if i else closes[i]; bp[i]=closes[i]-min(lows[i],prev); tr[i]=max(highs[i],prev)-min(lows[i],prev)
    for i in range(long-1,len(closes)):
        def avg(p):
            t=sum(tr[i-p+1:i+1]); return sum(bp[i-p+1:i+1])/t if t else 0.0
        out[i]=100*(4*avg(short)+2*avg(medium)+avg(long))/7
    return out
