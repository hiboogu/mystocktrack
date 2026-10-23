# temporary fetch script v3
import sys, yfinance as yf, pandas as pd
pd.set_option("display.width",250); pd.set_option("display.max_rows",500); pd.set_option("display.max_columns",30)
US=["NVDA","INTC","MSTR","PATH","KBR","CRNC","SOUN","OWLS","AMD","HON","TRMB","IOT","META","CRWV","NBIS","LRCX","MSFT","GOOGL","TSLA","IBM","TXN","^GSPC","^IXIC","^DJI","^RUT","^SOX","RSP","SPY","^VIX","^TNX","^IRX","CL=F","BZ=F","BTC-USD","DX-Y.NYB"]
JP=["5803.T","5801.T","5802.T","8035.T","6920.T","6861.T","6857.T","^N225","1306.T","JPY=X"]
mode=sys.argv[1] if len(sys.argv)>1 else "all"
def rsi(c,n=14):
    d=c.diff(); u=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); l=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean(); return 100-100/(1+u/l)
def summary(t):
    h=yf.Ticker(t).history(period="1y",auto_adjust=False)
    if h.empty: print(t,"EMPTY"); return
    c=h["Close"]
    print(f"\n=== {t} ===")
    print(h[["Open","High","Low","Close","Volume"]].tail(6).round(3).to_string())
    print(f"MA5 {c.rolling(5).mean().iloc[-1]:.3f} MA20 {c.rolling(20).mean().iloc[-1]:.3f} MA50 {c.rolling(50).mean().iloc[-1]:.3f} MA200 {c.rolling(200).mean().iloc[-1]:.3f} RSI {rsi(c).iloc[-1]:.1f} vol/20d {h['Volume'].iloc[-1]/h['Volume'].iloc[-21:-1].mean():.2f} 52wH {h['High'].max():.3f} 52wL {h['Low'].min():.3f}")
tick = US+JP if mode=="all" else JP
for t in tick:
    try: summary(t)
    except Exception as e: print(t,"ERR",e)
if mode=="all":
    for t in ["NVDA","INTC","OWLS","MSTR","^GSPC","^SOX"]:
        try:
            h=yf.Ticker(t).history(period="2d",interval="30m",prepost=True)
            print(f"\n--- {t} 30m prepost ---"); print(h[["Open","High","Low","Close","Volume"]].tail(40).round(3).to_string())
        except Exception as e: print(t,"ERR",e)
    for t in ["NVDA","INTC","OWLS","MSTR","PATH","SOUN","CRNC","KBR","TXN","IBM","TSLA","MSFT","GOOGL","5803.T","^GSPC"]:
        try:
            tk=yf.Ticker(t)
            print(f"\n### NEWS {t}")
            for n in (tk.news or [])[:6]:
                c=n.get("content",n); print("-",c.get("pubDate",""),c.get("title"),"|",(c.get("canonicalUrl") or {}).get("url",""))
            try: print("calendar:",tk.calendar)
            except Exception as e: print("cal err",e)
        except Exception as e: print(t,"ERR",e)
for t in ["5803.T","^N225","8035.T","5801.T"]:
    try:
        h=yf.Ticker(t).history(period="2d",interval="15m")
        print(f"\n--- {t} 15m ---"); print(h[["Open","High","Low","Close","Volume"]].tail(60).round(1).to_string())
    except Exception as e: print(t,"ERR",e)
if mode=="jp":
    h=yf.Ticker("5803.T").history(period="1y")
    w=h["Close"].resample("W").agg(["min","max","last"])
    print("\n--- 5803.T weekly close min/max/last (1y) ---"); print(w.round(0).to_string())
    print("\n--- 5803.T daily lows last 90d sorted ---"); print(h["Low"].tail(90).nsmallest(10).round(0).to_string())
    for t in ["5803.T","8035.T","6920.T","5801.T","^N225","JPY=X"]:
        try:
            x=yf.Ticker(t).history(period="5d",interval="5m").loc[lambda d: d.index.date==d.index[-1].date()] if t!="JPY=X" else yf.Ticker(t).history(period="1d",interval="30m")
            print(f"\n--- {t} 5m today ---"); print(x[["Open","High","Low","Close","Volume"]].round(1).to_string())
        except Exception as e: print(t,"ERR",e)
    for t in ["NVDA","INTC","OWLS","^GSPC"]:
        try:
            x=yf.Ticker(t).history(period="1d",interval="30m",prepost=True)
            print(f"\n--- {t} latest ---"); print(x[["Close"]].tail(3).round(3).to_string())
        except Exception as e: print(t,"ERR",e)
    for f in ["NQ=F","ES=F"]:
        try: print(f, yf.Ticker(f).history(period="2d",interval="30m")["Close"].tail(2).round(2).to_string())
        except Exception as e: print(f,"ERR",e)
