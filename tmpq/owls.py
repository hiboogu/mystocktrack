import yfinance as yf, pandas as pd, numpy as np, json, urllib.request, warnings
warnings.filterwarnings("ignore"); pd.set_option("display.width",200); pd.set_option("display.max_rows",200)
t=yf.Ticker("OWLS")
m=t.history(period="2d",interval="5m",prepost=True)
print("=== 5m"); print(m[["Open","High","Low","Close","Volume"]].tail(60).round(3).to_string())
for tk in ["BTC-USD","CRCL","COIN","^IXIC","IWM"]:
    try: d=yf.Ticker(tk).history(period="3d"); print(tk, d.Close.round(2).tolist())
    except Exception as e: print(tk,e)
req=urllib.request.Request("https://data.sec.gov/submissions/CIK0002025416.json",headers={"User-Agent":"mystocktrack research hiboogu@users.noreply.github.com"})
j=json.load(urllib.request.urlopen(req)); r=j["filings"]["recent"]
print("=== EDGAR")
for i in range(40): print(r["filingDate"][i],r["form"][i],r["primaryDocument"][i],r["accessionNumber"][i],r.get("primaryDocDescription",[""]*40)[i])
try:
    n=t.get_news(count=20); print("=== NEWS")
    for x in n: c=x.get("content",x); print(c.get("pubDate"),c.get("title"))
except Exception as e: print("news err",e)
# GBM touch / end probabilities from S=3.075 over 1y
rng=np.random.default_rng(1); S0=3.075
for sig in [0.6,0.8,1.0,1.2]:
  for mu in [0.0,-0.2]:
    n=20000; steps=252; dt=1/252
    z=rng.standard_normal((n,steps)); lp=np.cumsum((mu-0.5*sig**2)*dt+sig*np.sqrt(dt)*z,axis=1)
    mx=np.exp(lp.max(1)); end=np.exp(lp[:,-1])
    print(f"sig {sig} mu {mu}: touch25 {(mx*S0>=25).mean():.3f} end25 {(end*S0>=25).mean():.3f} touch10x(30.75) {(mx>=10).mean():.3f} end<=2.68 {(end*S0<=2.68).mean():.3f} touch<=2.68 {(np.exp(lp.min(1))*S0<=2.68).mean():.3f} touch<=1.5 {(np.exp(lp.min(1))*S0<=1.5).mean():.3f}")
