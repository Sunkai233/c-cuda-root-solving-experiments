#!/usr/bin/env python3
"""Deterministic paired-bootstrap analysis of raw performance repetitions."""
from __future__ import annotations
import argparse,csv,json,random,statistics
from collections import defaultdict
from pathlib import Path

def quant(v,q):
    s=sorted(v);return s[min(len(s)-1,int(q*(len(s)-1)))]
def boot_median_ratio(a,b,seed=20260824,B=10000):
    if len(a)!=len(b):raise ValueError("unpaired repetitions")
    ratios=[x/y for x,y in zip(a,b)];rng=random.Random(seed);n=len(ratios);bs=[]
    for _ in range(B):bs.append(statistics.median(ratios[rng.randrange(n)] for _ in range(n)))
    return statistics.median(ratios),quant(bs,.025),quant(bs,.975)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("run_dir",type=Path);ap.add_argument("--bootstrap",type=int,default=10000);args=ap.parse_args()
    raw=list(csv.DictReader((args.run_dir/"performance_repetitions.csv").open()))
    groups=defaultdict(dict)
    for r in raw:groups[(r["domain"],int(r["n"]),r["method"],r["timing_kind"])][int(r["repetition"])]=float(r["value_ms"])
    bad=[k for k,v in groups.items() if len(v)!=30]
    if bad:raise SystemExit(f"incomplete repetition groups: {bad[:5]}")
    gpu_methods=["fp32","fp64","adaptive_frozen_v1","adaptive_no_gradient_gate"]
    rows=[]
    for domain,n,method,kind in sorted(groups):
        if method not in gpu_methods or kind not in ("kernel","e2e"):continue
        cpu=groups[(domain,n,"cpu_fp64_omp128","solve")];gpu=groups[(domain,n,method,kind)]
        a=[cpu[i] for i in range(30)];b=[gpu[i] for i in range(30)]
        med,lo,hi=boot_median_ratio(a,b,B=args.bootstrap,seed=20260824+n+len(domain)+len(method)+len(kind))
        rows.append({"domain":domain,"n":n,"method":method,"timing_kind":kind,"speedup_median":med,"ci95_low":lo,"ci95_high":hi,"significant_speedup":lo>1})
    with (args.run_dir/"speedup_bootstrap.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    cross={}
    domains=sorted({r["domain"] for r in rows})
    for d in domains:
        cand=sorted([r for r in rows if r["domain"]==d and r["method"]=="adaptive_frozen_v1" and r["timing_kind"]=="e2e"],key=lambda r:r["n"])
        cross[d]=next((r["n"] for i,r in enumerate(cand) if all(x["ci95_low"]>1 for x in cand[i:])),None)
    ab=[]
    for d in domains:
      ns=sorted({n for dom,n,m,k in groups if dom==d})
      for n in ns:
        frozen=groups[(d,n,"adaptive_frozen_v1","e2e")];off=groups[(d,n,"adaptive_no_gradient_gate","e2e")]
        med,lo,hi=boot_median_ratio([frozen[i] for i in range(30)],[off[i] for i in range(30)],B=args.bootstrap,seed=7+n)
        ab.append({"domain":d,"n":n,"frozen_over_no_gate":med,"ci95_low":lo,"ci95_high":hi})
    with (args.run_dir/"gradient_gate_ablation.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=ab[0].keys());w.writeheader();w.writerows(ab)
    result={"bootstrap_resamples":args.bootstrap,"raw_rows":len(raw),"groups":len(groups),"all_groups_have_30":not bad,"adaptive_e2e_sustained_crossover_ci_low_gt_1":cross}
    (args.run_dir/"analysis.json").write_text(json.dumps(result,indent=2),encoding="utf-8");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
