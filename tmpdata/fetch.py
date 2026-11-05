import yfinance as yf, pandas as pd
pd.set_option("display.width", 250)
for t in ["MSTR", "BTC-USD", "COIN", "IBIT", "QQQ"]:
    d = yf.download(t, start="2026-03-01", interval="1d", auto_adjust=False, progress=False)
    d.columns = [c[0] for c in d.columns] if isinstance(d.columns, pd.MultiIndex) else d.columns
    print(f"=== DAILY {t} rows={len(d)}")
    for i, r in d.iterrows():
        print(f"D,{t},{i.date()},{r.Open:.2f},{r.High:.2f},{r.Low:.2f},{r.Close:.2f},{int(r.Volume)}")
for t in ["MSTR", "BTC-USD"]:
    d = yf.download(t, start="2026-10-30", interval="1h", progress=False)
    d.columns = [c[0] for c in d.columns] if isinstance(d.columns, pd.MultiIndex) else d.columns
    print(f"=== HOURLY {t} rows={len(d)}")
    for i, r in d.iterrows():
        print(f"H,{t},{i},{r.Open:.2f},{r.High:.2f},{r.Low:.2f},{r.Close:.2f},{int(r.Volume)}")
