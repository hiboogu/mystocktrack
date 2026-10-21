import yfinance as yf, pandas as pd
pd.set_option('display.width',250); pd.set_option('display.max_columns',20); pd.set_option('display.max_rows',500)
us=['NVDA','INTC','MSTR','PATH','SOUN','KBR','OWLS','CRNC','CRWV','NBIS','AMD','HON','TRMB','IOT','META','^GSPC','^IXIC','^SOX','^VIX','^TNX','BTC-USD','QQQ','RSP','CL=F']
jp=['5803.T','6920.T','6861.T','8035.T','6857.T','^N225','JPY=X']
print('=== DAILY ===')
for t in us+jp:
    h=yf.Ticker(t).history(period='1y',interval='1d')
    if h.empty: print(t,'EMPTY'); continue
    c=h['Close']
    ma=lambda n: round(c.rolling(n).mean().iloc[-1],2)
    d=c.diff(); g=d.clip(lower=0).rolling(14).mean(); l=(-d.clip(upper=0)).rolling(14).mean(); rsi=round(100-100/(1+g.iloc[-1]/l.iloc[-1]),1)
    print(f'## {t} MA20={ma(20)} MA50={ma(50)} MA200={ma(200)} RSI14={rsi} 52wH={round(h.High.max(),2)} 52wL={round(h.Low.min(),2)} avgVol20={int(h.Volume.tail(20).mean())}')
    print(h[['Open','High','Low','Close','Volume']].tail(4).round(3).to_string())
print('=== 30m 10/20 ===')
for t in ['NVDA','INTC','CRWV','QQQ','^SOX']:
    h=yf.Ticker(t).history(period='2d',interval='30m')
    print('##',t); print(h[['Open','High','Low','Close','Volume']].round(2).tail(14).to_string())
print('=== PREMARKET 5m ===')
for t in ['NVDA','INTC','MSTR','PATH','SOUN','KBR','OWLS','CRNC','CRWV','NBIS','AMD','META','QQQ']:
    h=yf.Ticker(t).history(period='1d',interval='5m',prepost=True)
    if h.empty: print(t,'none'); continue
    print('##',t,'last',h.index[-1],round(h.Close.iloc[-1],3),'hi',round(h.High.max(),3),'lo',round(h.Low.min(),3))
for t in ['NQ=F','ES=F','YM=F']:
    h=yf.Ticker(t).history(period='2d',interval='5m')
    print('##',t,h.index[-1],round(h.Close.iloc[-1],2))
print('=== TOKYO 15m ===')
for t in ['5803.T','6920.T']:
    h=yf.Ticker(t).history(period='1d',interval='15m')
    print('##',t); print(h[['Open','High','Low','Close','Volume']].round(1).to_string())
print('=== META info ===')
i=yf.Ticker('META').info
for k in ['marketCap','trailingPE','forwardPE','targetMeanPrice']: print(k,i.get(k))
try: print(yf.Ticker('META').calendar)
except Exception as e: print(e)
