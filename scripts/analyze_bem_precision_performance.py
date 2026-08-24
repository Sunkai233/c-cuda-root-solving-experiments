#!/usr/bin/env python3
import argparse,csv,json,random,statistics
from collections import defaultdict
from pathlib import Path
def q(v,p):s=sorted(v);return s[int(p*(len(s)-1))]
def boot(a,b,seed,B=10000):r=[x/y for x,y in zip(a,b)];g=random.Random(seed);n=len(r);z=[statistics.median(r[g.randrange(n)] for _ in range(n)) for _ in range(B)];return statistics.median(r),q(z,.025),q(z,.975)
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();g=defaultdict(dict)
for r in csv.DictReader(open(a.run/'bem_precision_performance_repetitions.csv')):g[(r['method'],r['timing_kind'])][int(r['repetition'])]=float(r['value_ms'])
rows=[]
for m,k in sorted(g):
 x=[g[(m,k)][i] for i in range(30)];b=[g[('fp64',k)][i] for i in range(30)];md,lo,hi=boot(b,x,20260824+sum(map(ord,m+k)));rows.append({'method':m,'timing_kind':k,'median_ms':statistics.median(x),'fp64_over_method':md,'ci95_low':lo,'ci95_high':hi})
a.out.mkdir(parents=True,exist_ok=True)
with open(a.out/'bem_precision_performance_bootstrap.csv','w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(a.out/'bem_precision_performance_summary.json').write_text(json.dumps({'bootstrap_resamples':10000,'groups':len(g),'all_groups_have_30':all(len(x)==30 for x in g.values())},indent=2));print(json.dumps(rows,indent=2))
