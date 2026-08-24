#!/usr/bin/env python3
"""Paired-bootstrap analysis for the frozen GPU-only v3 performance matrix."""
import argparse,csv,json,random,statistics
from collections import defaultdict
from pathlib import Path

def q(v,p):
    s=sorted(v);return s[min(len(s)-1,int(p*(len(s)-1)))]
def boot_ratio(a,b,seed,B):
    ratios=[x/y for x,y in zip(a,b)];rng=random.Random(seed);n=len(ratios)
    z=[statistics.median(ratios[rng.randrange(n)] for _ in range(n)) for _ in range(B)]
    return statistics.median(ratios),q(z,.025),q(z,.975)
def main():
    p=argparse.ArgumentParser();p.add_argument('run_dir',type=Path);p.add_argument('--out',type=Path);p.add_argument('--bootstrap',type=int,default=10000);a=p.parse_args();out=a.out or a.run_dir;out.mkdir(parents=True,exist_ok=True)
    raw=list(csv.DictReader((a.run_dir/'performance_repetitions.csv').open()))
    g=defaultdict(dict)
    for r in raw:g[(r['domain'],int(r['n']),r['method'],r['timing_kind'])][int(r['repetition'])]=float(r['value_ms'])
    bad=[k for k,v in g.items() if len(v)!=30]
    if bad:raise SystemExit(f'incomplete groups: {bad[:5]}')
    methods=sorted({k[2] for k in g}); expected={'fp32','fp64','adaptive_frozen_v3','adaptive_no_gradient_gate_v3'}
    if set(methods)!=expected:raise SystemExit(f'unexpected methods: {methods}')
    rows=[]
    for d,n,m,k in sorted(g):
        vals=[g[(d,n,m,k)][i] for i in range(30)]
        base=[g[(d,n,'fp64',k)][i] for i in range(30)]
        med,lo,hi=boot_ratio(base,vals,20260824+n+sum(map(ord,d+m+k)),a.bootstrap)
        rows.append({'domain':d,'n':n,'method':m,'timing_kind':k,'median_ms':statistics.median(vals),'p05_ms':q(vals,.05),'p95_ms':q(vals,.95),'fp64_over_method_median':med,'ci95_low':lo,'ci95_high':hi})
    with (out/'gpu_v3_paired_bootstrap.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    abl=[]
    for d,n in sorted({(x[0],x[1]) for x in g}):
      for k in ('kernel','e2e'):
        frozen=[g[(d,n,'adaptive_frozen_v3',k)][i] for i in range(30)];off=[g[(d,n,'adaptive_no_gradient_gate_v3',k)][i] for i in range(30)]
        med,lo,hi=boot_ratio(frozen,off,7+n+sum(map(ord,d+k)),a.bootstrap)
        abl.append({'domain':d,'n':n,'timing_kind':k,'frozen_over_no_gate_median':med,'ci95_low':lo,'ci95_high':hi})
    with (out/'gpu_v3_gradient_gate_ablation.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=abl[0]);w.writeheader();w.writerows(abl)
    summary={'bootstrap_resamples':a.bootstrap,'raw_rows':len(raw),'groups':len(g),'all_groups_have_30':not bad,'methods':methods}
    (out/'gpu_v3_analysis.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
