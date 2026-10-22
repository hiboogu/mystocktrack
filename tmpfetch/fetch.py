import yfinance as yf, pandas as pd
pd.set_option("display.width",250); pd.set_option("display.max_rows",500); pd.set_option("display.max_columns",20)
def rsi(s,n=14):
    d=s.diff(); u=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); l=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+u/l)
daily=["NVDA","INTC","MSTR","PATH","KBR","CRNC","SOUN","OWLS","META","CRWV","NBIS","AMD","HON","TRMB","IOT","LRCX","TSLA","TXN","IBM","QQQ","SPY","RSP","IWM","^GSPC","^IXIC","^DJI","^RUT","^SOX","^VIX","^TNX","CL=F","BZ=F","BTC-USD","JPY=X","^N225","5803.T","6920.T","6861.T","8035.T","6857.T","5801.T","5802.T","NQ=F","ES=F"]
for t in daily:
    try:
        h=yf.Ticker(t).history(period="1y",auto_adjust=False)
        if h.empty: print("EMPTY",t); continue
        c=h["Close"]
        h["MA5"]=c.rolling(5).mean();h["MA20"]=c.rolling(20).mean();h["MA50"]=c.rolling(50).mean();h["MA200"]=c.rolling(200).mean();h["RSI"]=rsi(c);h["V20"]=h["Volume"].rolling(20).mean()
        h["chg%"]=c.pct_change()*100
        print("=====DAILY",t)
        print(h[["Open","High","Low","Close","Volume","chg%","MA5","MA20","MA50","MA200","RSI","V20"]].tail(12).round(3).to_string())
        print("52wHigh",round(h["High"].max(),3),"52wLow",round(h["Low"].min(),3))
    except Exception as e: print("ERR",t,e)
for t,iv,p in [("OWLS","5m","5d"),("NVDA","30m","3d"),("INTC","30m","3d"),("META","5m","2d"),("5803.T","5m","2d"),("6920.T","15m","2d"),("^N225","15m","2d"),("NVDA","5m","1d"),("CRWV","30m","2d"),("MSTR","30m","2d"),("PATH","30m","2d"),("SOUN","30m","2d")]:
    try:
        h=yf.Ticker(t).history(period=p,interval=iv,prepost=True)
        print("=====INTRA",t,iv); print(h[["Open","High","Low","Close","Volume"]].round(3).to_string())
    except Exception as e: print("ERR",t,e)
for t in ["OWLS","META","5803.T"]:
    try:
        tk=yf.Ticker(t)
        print("=====INFO",t)
        i=tk.info
        for k in ["shortName","marketCap","sharesOutstanding","floatShares","sharesShort","shortPercentOfFloat","averageVolume","averageVolume10days","fiftyTwoWeekHigh","fiftyTwoWeekLow","trailingPE","forwardPE","targetMeanPrice","heldPercentInsiders","heldPercentInstitutions","longBusinessSummary"]:
            print(k,i.get(k))
        print(tk.news[:10] if tk.news else None)
    except Exception as e: print("ERR",t,e)
