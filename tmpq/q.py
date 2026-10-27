import yfinance as yf, pandas as pd, warnings, json
warnings.filterwarnings("ignore")
pd.set_option("display.width",250); pd.set_option("display.max_rows",500)
T = "NVDA INTC MSTR PATH KBR CRNC SOUN OWLS ^GSPC ^IXIC ^DJI ^RUT ^SOX RSP ^VIX ^VIX9D ^TNX ^IRX CL=F BZ=F GC=F BTC-USD DX-Y.NYB FRVO IE DAL DHR DVN CRBG CIFR CLSK USAR FIVE SHLS MSFT GOOGL META AMZN AMD LRCX CRWV NBIS HON TRMB IOT GLW COHR LITE CLS ANET 5803.T ^N225 6920.T 5801.T JPY=X IBIT MARA RIOT".split()
d = yf.download(T, period="1y", interval="1d", group_by="ticker", auto_adjust=False, progress=False, threads=True)
def rsi(c,n=14):
    dl=c.diff(); up=dl.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); dn=(-dl.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean(); return 100-100/(1+up/dn)
rows=[]
for t in T:
    try:
        x=d[t].dropna(subset=["Close"]); c=x["Close"]
        rows.append(dict(t=t,date=str(c.index[-1].date()),o=x["Open"].iloc[-1],h=x["High"].iloc[-1],l=x["Low"].iloc[-1],c=c.iloc[-1],prev=c.iloc[-2],chg=(c.iloc[-1]/c.iloc[-2]-1)*100,d5=(c.iloc[-1]/c.iloc[-6]-1)*100,
          ma20=c.rolling(20).mean().iloc[-1],ma50=c.rolling(50).mean().iloc[-1],ma200=c.rolling(200).mean().iloc[-1] if len(c)>=200 else None,rsi=rsi(c).iloc[-1],
          vr=x["Volume"].iloc[-1]/x["Volume"].iloc[-21:-1].mean() if x["Volume"].iloc[-21:-1].mean()>0 else None,hi52=x["High"].max(),lo52=x["Low"].min()))
    except Exception as e: print("ERR",t,e)
df=pd.DataFrame(rows).set_index("t"); print(df.round(3).to_string())
print("\n=== last 4 daily closes")
for t in "NVDA INTC CRNC SOUN OWLS DAL FRVO IE USAR CIFR CLSK 5803.T".split():
    x=d[t].dropna(subset=["Close"]).tail(4); print(t, [(str(i.date()),round(r.Low,3),round(r.Close,3)) for i,r in x.iterrows()])
print("\n=== intraday 30m prepost")
for t in "NVDA INTC CRNC SOUN OWLS DAL USAR FRVO IE MSTR".split():
    try:
        x=yf.download(t,period="2d",interval="30m",prepost=True,progress=False,auto_adjust=False)
        x.columns=[c[0] if isinstance(c,tuple) else c for c in x.columns]
        x=x[x.index.tz_convert("America/New_York").date==x.index.tz_convert("America/New_York").date.max()]
        print("--",t); print(x[["Open","High","Low","Close","Volume"]].round(3).to_string())
    except Exception as e: print("ERR",t,e)
print("\n=== Fujikura/Nikkei 15m today")
for t in ["5803.T","^N225"]:
    try:
        x=yf.download(t,period="1d",interval="15m",progress=False,auto_adjust=False); x.columns=[c[0] if isinstance(c,tuple) else c for c in x.columns]; print("--",t); print(x[["Open","High","Low","Close"]].round(1).to_string())
    except Exception as e: print("ERR",t,e)
print("\n=== calendar & news")
for t in "NVDA INTC MSTR PATH KBR CRNC SOUN OWLS FRVO IE DAL DHR DVN CRBG CIFR CLSK USAR FIVE MSFT GOOGL META AMZN".split():
    tk=yf.Ticker(t)
    try: cal=tk.calendar; print("##",t,"ER:",cal.get("Earnings Date"),"EPSavg:",cal.get("Earnings Average"),"RevAvg:",cal.get("Revenue Average"))
    except Exception as e: print("##",t,"cal err",e)
    try:
        for n in (tk.news or [])[:6]:
            c=n.get("content",n); print("   *",c.get("pubDate") or c.get("providerPublishTime"),"|",(c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"),dict) else c.get("publisher"),"|",c.get("title"),"|",(c.get("canonicalUrl") or {}).get("url") if isinstance(c.get("canonicalUrl"),dict) else c.get("link"))
    except Exception as e: print("  news err",e)
