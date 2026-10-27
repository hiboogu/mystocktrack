import yfinance as yf, pandas as pd
pd.set_option("display.width",250)
T = "KBR MSTR PATH CRNC SOUN OWLS INTC NVDA ^GSPC ^IXIC ^DJI ^RUT ^SOX RSP ^VIX ^VIX9D ^TNX ^IRX CL=F BZ=F GC=F BTC-USD DX-Y.NYB MSFT GOOGL META AMZN AMD LRCX CRWV NBIS HON TRMB IOT GLW COHR CLS ANET DAL DHR DVN FIVE CRBG UAL XLE FRVO IE SHLS 5803.T 6920.T 6861.T 5801.T 5802.T 8035.T ^N225 1306.T JPY=X".split()
def rsi(c,n=14):
    d=c.diff(); u=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); l=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+u/l)
rows=[]
for t in T:
    try:
        h=yf.Ticker(t).history(period="1y",auto_adjust=False).dropna(subset=["Close"])
        c=h.Close; last=h.iloc[-1]; mv=h.Volume.iloc[-21:-1].mean()
        rows.append(dict(t=t,date=str(h.index[-1].date()),o=last.Open,hi=last.High,lo=last.Low,c=last.Close,prev=c.iloc[-2],d=100*(c.iloc[-1]/c.iloc[-2]-1),w=100*(c.iloc[-1]/c.iloc[-6]-1),ma20=c.rolling(20).mean().iloc[-1],ma50=c.rolling(50).mean().iloc[-1],ma200=c.rolling(200).mean().iloc[-1],rsi=rsi(c).iloc[-1],vr=last.Volume/mv if mv>0 else 0,vol=last.Volume,hi52=h.High.max(),lo52=h.Low.min()))
        print(t,"last5:",[round(x,3) for x in c.iloc[-5:]],[str(x.date()) for x in h.index[-5:]])
    except Exception as e: print(t,"ERR",e)
print(pd.DataFrame(rows).set_index("t").round(3).to_string())
for t in "NVDA INTC OWLS CRNC DAL FIVE DHR DVN CRBG FRVO IE MSTR".split():
    try:
        h=yf.Ticker(t).history(period="2d",interval="30m",prepost=True)
        print("== 30m",t); print(h[["Open","High","Low","Close","Volume"]].tail(34).round(3).to_string())
    except Exception as e: print(t,"ERR",e)
for t in ["5803.T","^N225","6920.T"]:
    h=yf.Ticker(t).history(period="2d",interval="15m")
    print("== 15m",t); print(h[["Open","High","Low","Close","Volume"]].round(1).to_string())
for t in "NVDA INTC OWLS CRNC KBR MSTR PATH SOUN DAL DHR DVN FIVE CRBG FRVO IE MSFT GOOGL AMZN META".split():
    try:
        tk=yf.Ticker(t)
        try: print("CAL",t,tk.calendar)
        except Exception as e: print("CAL",t,"ERR",e)
        for n in (tk.news or [])[:5]:
            c=n.get("content",n); p=c.get("provider"); u=c.get("canonicalUrl")
            print("NEWS",t,c.get("pubDate"),"|",c.get("title"),"|",p.get("displayName") if isinstance(p,dict) else "","|",u.get("url") if isinstance(u,dict) else "")
    except Exception as e: print(t,"ERR",e)
