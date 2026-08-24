#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,random,statistics
from collections import defaultdict
from pathlib import Path
def q(v,p):s=sorted(v);return s[min(len(s)-1,int(p*(len(s)-1)))]
def boot(a,b,seed,B):
 r=[x/y for x,y in zip(a,b)];g=random.Random(seed);n=len(r);z=[statistics.median(r[g.randrange(n)] for _ in range(n)) for _ in range(B)];return statistics.median(r),q(z,.025),q(z,.975)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('run_dir',type=Path);ap.add_argument('--bootstrap',type=int,default=10000);a=ap.parse_args();raw=list(csv.DictReader((a.run_dir/'df32_performance_repetitions.csv').open()));groups=defaultdict(dict)
 for r in raw:groups[(r['domain'],int(r['n']),r['method'],r['timing_kind'])][int(r['repetition'])]=float(r['value_ms'])
 bad=[k for k,v in groups.items() if len(v)!=30]
 if bad:raise SystemExit(f'incomplete: {bad[:5]}')
 rows=[]
 for d,n,m,k in sorted(groups):
  if m!='df32':continue
  fp=groups[(d,n,'fp64_equivalent',k)];ds=groups[(d,n,'df32',k)];med,lo,hi=boot([fp[i] for i in range(30)],[ds[i] for i in range(30)],20260824+n+len(d)+len(k),a.bootstrap);rows.append({'domain':d,'n':n,'timing_kind':k,'df32_speedup_vs_fp64':med,'ci95_low':lo,'ci95_high':hi,'df32_faster':lo>1})
 with (a.run_dir/'df32_speedup_bootstrap.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 cross={}
 for d in sorted({r['domain'] for r in rows}):
  x=sorted([r for r in rows if r['domain']==d and r['timing_kind']=='e2e'],key=lambda z:z['n']);cross[d]=next((r['n'] for i,r in enumerate(x) if all(t['ci95_low']>1 for t in x[i:])),None)
 out={'bootstrap_resamples':a.bootstrap,'raw_rows':len(raw),'groups':len(groups),'all_groups_have_30':not bad,'df32_e2e_sustained_crossover':cross};(a.run_dir/'df32_analysis.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
