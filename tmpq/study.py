import yfinance as yf, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore"); pd.set_option("display.width",220); pd.set_option("display.max_rows",300)
G={
"穩定幣/支付/小型金融科技":"OWLS CRCL PAYO PSFE PAYS RELY IMXI FLYW MQ DLO PAGS STNE GDOT MOGO DAVE OPRT OPFI LPRO PGY ML LC UPST AFRM SOFI HOOD TREE BLND PRCH UWMC GHLD MFH AIFU XYF CNF LX FINV QFIN YRD LU TIGR FUTU NU IREN BKKT LMND ROOT HIPO OPEN XYZ TOST BILL PYPL CPSS ATLC ENVA",
"加密金融/挖礦/幣股":"COIN MSTR MARA RIOT CLSK HUT BTBT CIFR WULF BITF HIVE BTCS SOS GREE CAN EBON BTDR CORZ APLD LMFA MIGI ANY NCTY GLXY ARBK SAI FUFU BTOG",
}
rows=[]
for g,s in G.items():
    tk=s.split(); data=yf.download(tk,period="max",auto_adjust=True,progress=False,threads=True)
    C=data["Close"]; H=data["High"]
    for t in C.columns:
        c=C[t].dropna(); h=H[t].reindex(c.index)
        c=c[c.index>="2012-01-01"]; h=h.reindex(c.index)
        if len(c)<260: continue
        lo=c.rolling(252,min_periods=120).min(); hi=c.rolling(252,min_periods=120).max()
        last=-10**9
        for i in range(120,len(c)-1):
            p=c.iloc[i]
            if p<=lo.iloc[i]*1.0001 and i-last>=63:
                last=i
                fut=c.iloc[i+1:i+127]; fh=h.iloc[i+1:i+127]
                full=len(fut)==126
                mxc=fut.max()/p; mxh=fh.max()/p; mn=fut.min()/p; end=fut.iloc[-1]/p
                # first passage: 2x before -50%?
                hit2=np.where(fut.values>=2*p)[0]; dn50=np.where(fut.values<=0.5*p)[0]; dn30=np.where(fut.values<=0.7*p)[0]
                rows.append(dict(g=g,t=t,d=c.index[i].date(),p=round(p,3),dd=p/hi.iloc[i]-1,full=full,mxc=mxc,mxh=mxh,mn=mn,end=end,
                  t2=hit2[0]+1 if len(hit2) else np.nan,
                  first2=(len(hit2)>0) and (len(dn50)==0 or hit2[0]<dn50[0]),
                  dn30=len(dn30)>0, dn30_then2=(len(dn30)>0 and len(hit2)>0 and hit2[0]>dn30[0])))
df=pd.DataFrame(rows); df=df[df.full]
df["yr"]=pd.to_datetime(df.d).dt.year
def summ(x,name):
    n=len(x); 
    if n==0: return
    print(f"{name:42s} n={n:4d} 收盤曾達2x {(x.mxc>=2).mean():.3f} 盤中曾達2x {(x.mxh>=2).mean():.3f} 6月後仍>=2x {(x.end>=2).mean():.3f} 曾達1.5x {(x.mxc>=1.5).mean():.3f} 6月後中位 {x.end.median():.2f} 6月後<0.5 {(x.end<0.5).mean():.3f} 先再跌30% {x.dn30.mean():.3f} 先跌30%後仍2x {x.dn30_then2.mean():.3f} 2x天數中位 {x.t2.median():.0f}")
print("=== ALL"); summ(df,"全部")
for g in G: summ(df[df.g==g],g)
print("=== 依距52週高點跌幅")
for a,b in [(-1,-0.75),(-0.75,-0.6),(-0.6,-0.4),(-0.4,0)]: summ(df[(df.dd>a)&(df.dd<=b)],f"跌幅 {a:.0%}~{b:.0%}")
print("=== 依股價")
for a,b in [(0,1),(1,5),(5,20),(20,1e9)]: summ(df[(df.p>=a)&(df.p<b)],f"價 {a}-{b}")
print("=== OWLS-like: 跌幅>=70% 且 價<5")
x=df[(df.dd<=-0.7)&(df.p<5)]; summ(x,"跌幅>=70% 且價<5"); 
for g in G: summ(x[x.g==g],"  "+g)
print("=== 依年份 (全部)")
for y,x2 in df.groupby("yr"): summ(x2,str(y))
print("=== 依年份 (跌幅>=70%且價<5)")
for y,x2 in x.groupby("yr"): summ(x2,str(y))
print("=== 排除2020/3-4月與2022-12~2023-1（大盤/加密V反轉）")
mask=~((pd.to_datetime(df.d)>="2020-02-15")&(pd.to_datetime(df.d)<="2020-04-30")) & ~((pd.to_datetime(df.d)>="2022-11-01")&(pd.to_datetime(df.d)<="2023-01-31"))
summ(df[mask],"全部(排除)"); summ(x[mask.reindex(x.index)],"跌幅>=70%且價<5(排除)")
print("=== 成功案例 (跌幅>=70% 價<5, 收盤曾達2x)")
print(x[x.mxc>=2][["t","g","d","p","dd","mxc","end","t2"]].round(2).sort_values("d").to_string())
print("=== 失敗案例樣本 (跌幅>=70% 價<5, 6月後<0.5)")
print(x[x.end<0.5][["t","d","p","dd","mxc","end"]].round(2).sort_values("d").tail(40).to_string())
print("tickers used", df.t.nunique(), sorted(df.t.unique()))
o=yf.Ticker("OWLS").history(period="5d",interval="5m"); print("=== OWLS now"); print(o.tail(12)[["Close","Low","Volume"]].round(3).to_string())
