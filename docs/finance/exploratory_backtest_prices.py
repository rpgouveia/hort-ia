# Backtest de precos (9.6.1-1/9.6.1-3). Uso: python3 9.6.1-3_backtest_precos.py prices_monthly.csv
# Dados: data/market/prices_monthly.csv do repositorio hort-ia (origin/main, commit 10cdcb0, Fernando)
import sys
import pandas as pd, numpy as np, itertools, json
df=pd.read_csv(sys.argv[1] if len(sys.argv)>1 else 'prices.csv'); months=pd.period_range('2024-08','2026-08',freq='M')
piv=df.pivot_table(index=['product_id','entrepost_id'],columns='month',values='price_brl_kg')
piv=piv.reindex(columns=[str(m) for m in months])
cnt=piv.notna().sum(axis=1); print(cnt.describe()); 
ser=piv[cnt>=22]  # series with >= 22 observed months; print('series>=22:',len(ser),'of',len(piv))
def fill(y):
    s=pd.Series(y); s=s.loc[s.first_valid_index():s.last_valid_index()]  # edges are never extended
    return s.interpolate().values
def ses(y,a):
    l=y[0]
    for v in y[1:]: l=a*v+(1-a)*l
    return l
def fit_ses(y):
    best=min(np.arange(.1,1.0,.1),key=lambda a:sum((y[i]-ses(y[:i],a))**2 for i in range(3,len(y))));return best
def holt_d(y,h):
    best=None
    for a,b,p in itertools.product([.2,.5,.8],[.1,.3],[.8,.95]):
        l,t=y[0],y[1]-y[0];e=0
        for v in y[1:]:
            f=l+p*t;e+=(v-f)**2;ln=a*v+(1-a)*(l+p*t);t=b*(ln-l)+(1-b)*p*t;l=ln
        if best is None or e<best[0]:best=(e,a,b,p,l,t)
    _,a,b,p,l,t=best;return l+sum(p**k for k in range(1,h+1))*t
def preds(y,h):
    n=len(y);o={}
    o['naive']=y[-1]; o['mm3']=y[-3:].mean()
    o['snaive']=y[n+h-1-12] if n+h-1-12<n else y[-1]
    o['ses']=ses(y,fit_ses(y)); o['holt_amort']=holt_d(y,h)
    # ETS-like: SES level scaled by last-year seasonal ratio
    o['ses_sazonal']=ses(y,fit_ses(y))*(y[n+h-1-12]/y[n-1-12]) if n>=13+h-1 and n+h-1-12<n else o['ses']
    return o
res={h:{} for h in (1,3)}
for h in (1,3):
  for idx,row in ser.iterrows():
    y=fill(row.values.astype(float))
    for o in range(15,len(y)-h+1):   # >=15 obs training
      p=preds(y[:o],h);act=y[o+h-1]
      for k,v in p.items(): res[h].setdefault(k,[]).append((abs(v-act),abs(v-act)/act))
for h in (1,3):
  print('h',h)
  for k,v in sorted(res[h].items(),key=lambda kv:np.mean([x[0] for x in kv[1]])):
    a=np.array(v);print(f'  {k:12s} MAE={a[:,0].mean():.3f} MAPE={100*a[:,1].mean():.1f}% n={len(a)}')
print('--- por produto')
rows=[]
for h in (1,3):
  for prod in ser.index.get_level_values(0).unique():
    for k in ('naive','ses','snaive','mm3'):
      e=[]
      for idx,row in ser.loc[[prod]].iterrows():
        y=fill(row.values.astype(float))
        for o in range(15,len(y)-h+1):
          e.append(abs(preds(y[:o],h)[k]-y[o+h-1])/y[o+h-1])
      rows.append((h,prod,k,100*np.mean(e)))
t=pd.DataFrame(rows,columns=['h','prod','m','mape']).pivot_table(index=['h','prod'],columns='m',values='mape').round(1);print(t)
