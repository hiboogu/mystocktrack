import yfinance as yf, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from math import sqrt
def get(t,start="2020-09-01"):
    d=yf.download(t,start=start,auto_adjust=True,progress=False)
    if isinstance(d.columns,pd.MultiIndex): d.columns=[c[0] for c in d.columns]
    return d
M=get("MSTR"); B=get("BTC-USD"); Q=get("QQQ"); I=get("IBIT","2024-01-11")
df=pd.DataFrame({"m":M.Close,"mh":M.High,"ml":M.Low,"mv":M.Volume,"q":Q.Close}).dropna()
df["b"]=B.Close.reindex(df.index)  # BTC UTC-midnight close ~3-4h after US close
df=df.dropna()
print("rows",len(df),df.index[0].date(),df.index[-1].date())
r=np.log(df[["m","b","q"]]).diff()
def ci(p,n): s=1.96*sqrt(p*(1-p)/n); return f"{p*100:.1f}% (95%CI {100*(p-s):.0f}-{100*(p+s):.0f}%, n={n})"
print("\n## A. SAME-DAY (needs knowing BTC's move) — rolling 252d OLS, out-of-sample")
for lab,x,y in [("daily BTC-USD",r.b,r.m),("daily QQQ only",r.q,r.m)]:
    pred=[];act=[]
    for i in range(252,len(r)):
        w=pd.concat([x.iloc[i-252:i],y.iloc[i-252:i]],axis=1).dropna()
        bt=np.polyfit(w.iloc[:,0],w.iloc[:,1],1); pred.append(np.polyval(bt,x.iloc[i])); act.append(y.iloc[i])
    pred=np.array(pred);act=np.array(act); ok=~np.isnan(pred)&~np.isnan(act); pred,act=pred[ok],act[ok]
    r2=1-((act-pred)**2).sum()/((act-act.mean())**2).sum()
    print(lab,"OOS R2",round(r2,3),"direction hit",ci(np.mean(np.sign(pred)==np.sign(act)),len(act)))
# two-factor
X=pd.concat([r.b,r.q],axis=1); pred=[];act=[]
for i in range(252,len(r)):
    w=pd.concat([X.iloc[i-252:i],r.m.iloc[i-252:i]],axis=1).dropna(); A=np.c_[np.ones(len(w)),w.iloc[:,:2]]
    co=np.linalg.lstsq(A,w.iloc[:,2],rcond=None)[0]; pred.append(co@np.r_[1,X.iloc[i]]); act.append(r.m.iloc[i])
pred=np.array(pred);act=np.array(act); r2=1-((act-pred)**2).sum()/((act-act.mean())**2).sum()
print("daily BTC+QQQ OOS R2",round(r2,3),"direction hit",ci(np.mean(np.sign(pred)==np.sign(act)),len(act)))
if len(I):
    j=pd.concat([np.log(M.Close).diff().rename("m"),np.log(I.Close).diff().rename("i")],axis=1).dropna()
    pred=[];act=[]
    for k in range(126,len(j)):
        w=j.iloc[k-126:k]; bt=np.polyfit(w.i,w.m,1); pred.append(np.polyval(bt,j.i.iloc[k])); act.append(j.m.iloc[k])
    pred=np.array(pred);act=np.array(act); r2=1-((act-pred)**2).sum()/((act-act.mean())**2).sum()
    print("daily IBIT (same close time) OOS R2",round(r2,3),"direction hit",ci(np.mean(np.sign(pred)==np.sign(act)),len(act)))
    big=np.abs(pred)>0.03; print("  when predicted |move|>3%: hit",ci(np.mean(np.sign(pred[big])==np.sign(act[big])),big.sum()))
wk=np.log(df[["m","b"]].resample("W-FRI").last()).diff().dropna()
pred=[];act=[]
for i in range(52,len(wk)):
    w=wk.iloc[i-52:i]; bt=np.polyfit(w.b,w.m,1); pred.append(np.polyval(bt,wk.b.iloc[i])); act.append(wk.m.iloc[i])
pred=np.array(pred);act=np.array(act); r2=1-((act-pred)**2).sum()/((act-act.mean())**2).sum()
print("weekly BTC OOS R2",round(r2,3),"direction hit",ci(np.mean(np.sign(pred)==np.sign(act)),len(act)))
# by year
print("rolling 1y beta/R2 by year:")
for y,g in r.dropna().groupby(r.dropna().index.year):
    c=g.m.corr(g.b); print(" ",y,"beta",round(g.m.cov(g.b)/g.b.var(),2),"R2",round(c*c,2),"n",len(g))

print("\n## B. FORECAST (only info known at close t) — walk-forward, retrain every 21d, first 2y train")
f=pd.DataFrame(index=df.index)
lm=np.log(df.m); lb=np.log(df.b); lq=np.log(df.q)
for n in (1,5,20): f[f"m{n}"]=lm.diff(n); f[f"b{n}"]=lb.diff(n)
f["q5"]=lq.diff(5)
for n in (20,50,200): f[f"dma{n}"]=lm-np.log(df.m.rolling(n).mean())
d=df.m.diff(); u=d.clip(lower=0).ewm(alpha=1/14).mean(); dn=(-d.clip(upper=0)).ewm(alpha=1/14).mean(); f["rsi"]=100-100/(1+u/dn)
prem=lm-lb; f["premz"]=(prem-prem.rolling(120).mean())/prem.rolling(120).std()
f["vol20"]=lm.diff().rolling(20).std(); f["vr"]=df.mv/df.mv.rolling(20).mean()
f["bdma50"]=lb-np.log(df.b.rolling(50).mean())
feats=list(f.columns)
for H in (1,5,20):
    y=(lm.shift(-H)-lm>0).astype(float); y[lm.shift(-H).isna()]=np.nan
    data=pd.concat([f,y.rename("y")],axis=1).dropna()
    start=504; res={}
    for name,mk in [("logit",lambda:make_pipeline(StandardScaler(),LogisticRegression(C=0.1,max_iter=500))),("gbm",lambda:GradientBoostingClassifier(n_estimators=150,max_depth=2,learning_rate=0.05,subsample=0.8,random_state=0))]:
        P=pd.Series(np.nan,index=data.index)
        for s in range(start,len(data),21):
            tr=data.iloc[:max(s-H,1)]; te=data.iloc[s:s+21]
            mdl=mk().fit(tr[feats],tr.y); P.iloc[s:s+21]=mdl.predict_proba(te[feats])[:,1]
        ev=data.iloc[start:].copy(); ev["p"]=P.iloc[start:]
        step=ev.iloc[::H]  # non-overlapping
        base=step.y.mean(); hit=((step.p>0.5)==(step.y==1)).mean()
        conf=step[(step.p>0.6)|(step.p<0.4)]; ch=((conf.p>0.5)==(conf.y==1)).mean() if len(conf) else np.nan
        conf7=step[(step.p>0.7)|(step.p<0.3)]; ch7=((conf7.p>0.5)==(conf7.y==1)).mean() if len(conf7) else np.nan
        print(f"H={H}d {name}: up base rate {base*100:.1f}%, hit {ci(hit,len(step))}; |p-0.5|>0.1: {ci(ch,len(conf)) if len(conf) else 'none'}; >0.2: {ci(ch7,len(conf7)) if len(conf7) else 'none'}")
        # calibration of claimed 70%
    print(f"  always-up hit = {base*100:.1f}%")

print("\n## C. RULES (technical levels), MSTR since 2021")
ma20=df.m.rolling(20).mean(); fwd5=df.m.shift(-5)/df.m-1
rej=(df.mh>=ma20)&(df.m<ma20)&(df.m.shift(1)<ma20.shift(1))
x=fwd5[rej].dropna(); print("touch 20MA from below & close under -> next 5d down:",ci((x<0).mean(),len(x)),"avg",round(x.mean()*100,2),"%")
allx=fwd5.dropna(); print("  unconditional 5d down:",ci((allx<0).mean(),len(allx)))
cross=(df.m>ma20)&(df.m.shift(1)<ma20.shift(1)); x=fwd5[cross].dropna(); print("close crosses above 20MA -> next 5d up:",ci((x>0).mean(),len(x)))
dd=f.rsi<30; x=fwd5[dd].dropna(); print("RSI<30 -> next 5d up:",ci((x>0).mean(),len(x)))
fwd20=lm.shift(-20)-lm-(lb.shift(-20)-lb)
for th in (-1.5,1.5):
    sel=(f.premz<th) if th<0 else (f.premz>th); x=fwd20[sel].dropna()
    print(f"premium z {'<' if th<0 else '>'}{th} -> next 20d MSTR beats BTC:",ci((x>0).mean(),len(x)),"avg rel",round(x.mean()*100,1),"%")
print("\nlatest features:"); print(f.iloc[-1].round(3).to_string())
