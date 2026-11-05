import yfinance as yf, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
from math import sqrt
def get(t,iv,period,pp=False):
    d=yf.download(t,period=period,interval=iv,prepost=pp,progress=False,auto_adjust=True)
    if isinstance(d.columns,pd.MultiIndex): d.columns=[c[0] for c in d.columns]
    d.index=d.index.tz_convert("America/New_York"); return d
def ci(p,n): s=1.96*sqrt(p*(1-p)/n); return f"{p*100:.1f}% ({100*(p-s):.0f}-{100*(p+s):.0f}%, n={n})"
def reg(x,y,lab):
    m=~(np.isnan(x)|np.isnan(y)); x,y=x[m],y[m]; b=np.polyfit(x,y,1); c=np.corrcoef(x,y)[0,1]
    hit=np.mean(np.sign(x)==np.sign(y)); big=np.abs(x)>np.std(x)
    hb=np.mean(np.sign(x[big])==np.sign(y[big]))
    t=c*sqrt((len(x)-2)/(1-c*c))
    print(f"{lab}: beta {b[0]:.2f}, corr {c:.3f} (t={t:.1f}), R2 {c*c:.3f}, same-sign {ci(hit,len(x))}, when |x|>1sd {ci(hb,big.sum())}")
M=get("MSTR","1h","730d"); B=get("BTC-USD","1h","730d")
print("MSTR 1h",M.index[0],M.index[-1],len(M)," BTC 1h",len(B))
reg_=M[(M.index.hour>=9)&(M.index.hour<16)]
days=sorted(set(reg_.index.date))
rows=[]
bo=B.Open
def bat(ts):
    try: return bo.loc[ts]
    except KeyError: return np.nan
for i in range(1,len(days)):
    d0,d1=days[i-1],days[i]
    a=reg_[reg_.index.date==d0]; c=reg_[reg_.index.date==d1]
    if len(a)<6 or len(c)<6: continue
    pc=a.Close.iloc[-1]; op=c.Open.iloc[0]; cl=c.Close.iloc[-1]; h1=c.Close.iloc[0]
    tz="America/New_York"
    b16=bat(pd.Timestamp(f"{d0} 16:00",tz=tz)); b9=bat(pd.Timestamp(f"{d1} 09:00",tz=tz)); b10=bat(pd.Timestamp(f"{d1} 10:00",tz=tz)); b16b=bat(pd.Timestamp(f"{d1} 16:00",tz=tz))
    rows.append(dict(d=d1,gap=np.log(op/pc),oc=np.log(cl/op),fh=np.log(h1/op),rest=np.log(cl/h1),
        bn=np.log(b9/b16),bday=np.log(b16b/b9),bfirst=np.log(b10/b9),wkend=(pd.Timestamp(d1)-pd.Timestamp(d0)).days>1))
D=pd.DataFrame(rows).dropna(); print("days",len(D))
print("\n## 1. Overnight BTC (prev 16:00 ET -> 09:00 ET) vs MSTR open gap")
reg(D.bn.values,D.gap.values,"all days")
reg(D[D.wkend].bn.values,D[D.wkend].gap.values,"after weekend/holiday")
print("share of MSTR close-to-close variance from gap:",round(D.gap.var()/(D.gap+D.oc).var(),2))
print("\n## 2. Does overnight BTC predict MSTR AFTER the open? (tradable edge test)")
reg(D.bn.values,D.oc.values,"overnight BTC -> MSTR open->close")
reg(D.bn.values,D.fh.values,"overnight BTC -> MSTR first hour")
r=D.gap-1.6*D.bn
reg(r.values,D.oc.values,"gap residual (over/under-reaction) -> open->close")
reg(D.gap.values,D.oc.values,"gap -> open->close (fade/continue)")
print("\n## 3. Same-session: BTC 09:00-16:00 vs MSTR open->close")
reg(D.bday.values,D.oc.values,"same hours")
# hourly lead-lag regular session
Mh=reg_.Close; rm=np.log(Mh).diff(); rm[rm.index.hour==9]=np.nan
Bh=B.Close; rb=np.log(Bh).diff()
print("\n## 4. Hourly lead-lag (regular hours)")
for L in (-1,0,1,2):
    # BTC return in hour shifted by L hours relative to MSTR hour
    x=[];y=[]
    for ts,v in rm.dropna().items():
        t2=ts.floor("h")-pd.Timedelta(hours=L)  # L>0 => BTC earlier
        if t2 in rb.index: x.append(rb.loc[t2]); y.append(v)
    x=np.array(x);y=np.array(y); m=~np.isnan(x); c=np.corrcoef(x[m],y[m])[0,1]; print(f" BTC lag {L}h (positive=BTC earlier): corr {c:.3f}, n={m.sum()}")
print("\n## 5. 5-minute lead-lag (last ~60 days, regular hours)")
M5=get("MSTR","5m","60d"); B5=get("BTC-USD","5m","60d")
m5=M5[(M5.index.time>=pd.Timestamp('09:35').time())&(M5.index.hour<16)].Close
j=pd.concat([np.log(M5.Close).diff().rename("m"),np.log(B5.Close).diff().rename("b")],axis=1)
j=j.loc[j.index.isin(m5.index)]
bfull=np.log(B5.Close).diff()
for L in (-2,-1,0,1,2,3,6):
    bb=bfull.shift(L).reindex(j.index); c=j.m.corr(bb); n=bb.notna().sum(); print(f" BTC lag {L*5}min: corr {c:.3f} (t~{c*sqrt(n):.1f}), n={n}")
# edge: BTC last 5m move > 0.3% -> MSTR next 5m
bb=bfull.reindex(j.index); nxt=j.m.shift(-1)
for th in (0.002,0.004):
    sel=bb.abs()>th; x=(np.sign(bb[sel])==np.sign(nxt[sel])).mean(); avg=(np.sign(bb[sel])*nxt[sel]).mean()
    print(f" |BTC 5m|>{th*100:.1f}% -> MSTR next 5m same dir {ci(x,sel.sum())}, avg follow-through {avg*100:.3f}%")
