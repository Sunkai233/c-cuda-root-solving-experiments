#!/usr/bin/env python3
import argparse,csv,json,random,statistics
from pathlib import Path
def q(v,p):s=sorted(v);return s[int(p*(len(s)-1))]
def boot(a,b,seed,B=10000):
 r=[x/y for x,y in zip(a,b)];g=random.Random(seed);n=len(r);z=[statistics.median(r[g.randrange(n)] for _ in range(n)) for _ in range(B)];return statistics.median(r),q(z,.025),q(z,.975)
p=argparse.ArgumentParser();p.add_argument('json',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();x=json.loads(a.json.read_text());rows=[]
for name,base,cand,label in [('fusion','split_times_ms','fused_times_ms','split/fused'),('gradient','unrolled_times_ms','implicit_times_ms','unrolled/implicit'),('trig','direct_times_ms','recurrence_times_ms','direct/recurrence')]:
 m,l,h=boot(x[name][base],x[name][cand],20260824+len(name));rows.append({'ablation':name,'ratio':label,'median':m,'ci95_low':l,'ci95_high':h})
a.out.mkdir(parents=True,exist_ok=True)
with (a.out/'remaining_ablation_bootstrap.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(a.out/'remaining_ablation_metrics.json').write_text(json.dumps(x,indent=2),encoding='utf-8');print(json.dumps(rows,indent=2))
