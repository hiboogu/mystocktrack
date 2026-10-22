import yfinance as yf, pandas as pd, numpy as np, json, warnings
warnings.filterwarnings("ignore")
pd.set_option("display.width",250); pd.set_option("display.max_columns",30); pd.set_option("display.max_rows",400)
t=yf.Ticker("OWLS")
h=t.history(period="max",auto_adjust=False)
print("=== HIST rows",len(h)); print(h[["Open","High","Low","Close","Volume"]].resample("W").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).to_string())
print(h.tail(8).to_string())
try:
    i=t.get_info(); print("=== INFO"); print(json.dumps({k:v for k,v in i.items() if not isinstance(v,(list,dict))},default=str,indent=0)[:8000])
except Exception as e: print("info err",e)
for name in ["quarterly_income_stmt","income_stmt","quarterly_balance_sheet","balance_sheet","quarterly_cashflow","cashflow"]:
    try: print("===",name); print(getattr(t,name).to_string())
    except Exception as e: print(name,"err",e)
try:
    print("=== OPTIONS",t.options)
    for d in t.options[:6]:
        c=t.option_chain(d); print("EXP",d); print(c.calls[["strike","lastPrice","bid","ask","volume","openInterest","impliedVolatility"]].to_string())
except Exception as e: print("opt err",e)
for k in ["earnings_dates","calendar","major_holders","institutional_holders","insider_transactions","analyst_price_targets","recommendations"]:
    try: print("===",k); print(getattr(t,k))
    except Exception as e: print(k,"err",e)
try:
    n=t.news; print("=== NEWS"); [print(x.get("content",{}).get("pubDate"),x.get("content",{}).get("title")) for x in n[:15]]
except Exception as e: print("news err",e)
r=np.log(h.Close).diff().dropna()
print("=== OWLS vol: 20d %.2f 60d %.2f  120d %.2f  all %.2f"%(r[-20:].std()*252**.5,r[-60:].std()*252**.5, r[-120:].std()*252**.5, r.std()*252**.5))
basket="SOUN CRNC BBAI RGTI QUBT IONQ KULR LAZR GOEV OPEN SOFI UPST AFRM MARA RIOT CLSK HUT BTBT CIFR WULF BITF HIVE SDIG GREE CAN EBON SOS BTCS MSTR COIN HOOD DAVE MQ PAYO FLYW PSFE OLO BMBL LMND ROOT HIPO OSCR CLOV SKLZ PLBY WKHS CHPT BLNK QS STEM LCID RIVN ASTS SPCE RKLB PL BKSY VLD ACHR JOBY EVTL DM CVNA GRAB NU PAGS STNE MOGO OPRT LC TREE UWMC RKT BLND PGY PRCH IREN APLD BTDR CORZ BFLY QSI SNDL TLRY CGC ACB PTON MVIS IDEX OCGN NNDM GEVO FCEL PLUG RUN SPWR".split()
data=yf.download(basket,period="10y",auto_adjust=True,progress=False,threads=True)["Close"]
ev=0;hit3=hit6=hit10=end6=end10=0;rets=[];peryr={};tk_hits={}
for tk in data.columns:
    s=data[tk].dropna()
    if len(s)<600: continue
    hi=s.rolling(252).max(); lo=s.rolling(252).min()
    last=-999
    for i in range(252,len(s)-252):
        p=s.iloc[i]
        if p<=lo.iloc[i]*1.001 and p<=hi.iloc[i]*0.35 and i-last>=63:
            last=i; ev+=1
            fut=s.iloc[i+1:i+253]; m=fut.max()/p; e=fut.iloc[-1]/p
            hit3+=m>=3; hit6+=m>=6; hit10+=m>=10; end6+=e>=6; end10+=e>=10; rets.append(e)
            y=s.index[i].year; peryr.setdefault(y,[0,0]); peryr[y][0]+=1; peryr[y][1]+=int(m>=6)
            if m>=6: tk_hits.setdefault(tk,[]).append(str(s.index[i].date()))
rets=np.array(rets)
print("=== BASE RATE events",ev,"tickers",data.shape[1])
print("touch>=3x %.3f touch>=6x %.3f touch>=10x %.3f | end>=3x %.3f end>=6x %.3f end>=10x %.3f"%(hit3/ev,hit6/ev,hit10/ev,(rets>=3).mean(),end6/ev,end10/ev))
print("end ret quantiles 5..99", np.percentile(rets,[5,10,25,50,75,90,95,99]).round(2), "P(end<0.5) %.3f P(end<0.674) %.3f mean %.2f"%((rets<0.5).mean(),(rets<0.674).mean(),rets.mean()))
print("by year",peryr); print("6x hits",tk_hits)
