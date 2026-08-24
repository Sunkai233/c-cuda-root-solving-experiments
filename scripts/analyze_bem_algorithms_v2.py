#!/usr/bin/env python3
import argparse,csv,json,random,statistics
from pathlib import Path
def q(v,p):s=sorted(v);return s[int(p*(len(s)-1))]
def boot(a,b,seed):r=[x/y for x,y in zip(a,b)];g=random.Random(seed);n=len(r);z=[statistics.median(r[g.randrange(n)] for _ in range(n)) for _ in range(10000)];return statistics.median(r),q(z,.025),q(z,.975)
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();names={0:'bisection',1:'brent',2:'illinois',3:'fixed44',4:'adaptive_compacted'};x={i:json.load(open(a.run/f'performance_alg{i}.json')) for i in names};rows=[]
for i,n in names.items():
 for kind,key in [('kernel','kernel_times_ms'),('e2e','end_to_end_times_ms')]:
  m,l,h=boot(x[1][key],x[i][key],20260824+i+len(kind));rows.append({'method':n,'timing_kind':kind,'median_ms':statistics.median(x[i][key]),'brent_over_method':m,'ci95_low':l,'ci95_high':h})
a.out.mkdir(parents=True,exist_ok=True)
with open(a.out/'bem_algorithms_v2_bootstrap.csv','w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print(json.dumps(rows,indent=2))
