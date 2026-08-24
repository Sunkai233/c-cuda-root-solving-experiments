#!/usr/bin/env python3
"""Deterministic paired-bootstrap analysis for the strict FP64 algorithm matrix."""
from __future__ import annotations
import argparse,csv,json,statistics
from collections import defaultdict
from pathlib import Path
import numpy as np

def quant(values,q):
    s=sorted(values);return s[min(len(s)-1,int(q*(len(s)-1)))]
def bootstrap_ratio(numerator,denominator,seed,resamples):
    ratios=np.asarray(numerator)/np.asarray(denominator);rng=np.random.default_rng(seed);n=len(ratios)
    indexes=rng.integers(0,n,size=(resamples,n));boots=np.median(ratios[indexes],axis=1)
    return statistics.median(ratios),quant(boots,.025),quant(boots,.975)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("run_dir",type=Path);ap.add_argument("--bootstrap",type=int,default=10000);args=ap.parse_args()
    path=args.run_dir/"algorithm_performance_repetitions.csv";raw=list(csv.DictReader(path.open()))
    groups=defaultdict(dict)
    for row in raw:groups[(row["domain"],int(row["n"]),row["method"],row["timing_kind"])][int(row["repetition"])]=float(row["value_ms"])
    incomplete=[k for k,v in groups.items() if len(v)!=30]
    if incomplete:raise SystemExit(f"incomplete repetition groups: {incomplete[:5]}")
    rows=[]
    for domain,n,method,kind in sorted(groups):
        if method=="brent_dekker":continue
        base=groups[(domain,n,"brent_dekker",kind)];candidate=groups[(domain,n,method,kind)]
        med,lo,hi=bootstrap_ratio([base[i] for i in range(30)],[candidate[i] for i in range(30)],20260824+n+len(domain)+len(method)+len(kind),args.bootstrap)
        rows.append({"domain":domain,"n":n,"method":method,"timing_kind":kind,"speedup_vs_brent":med,"ci95_low":lo,"ci95_high":hi,"faster_than_brent":lo>1})
    with (args.run_dir/"algorithm_speedup_bootstrap.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    summary={"bootstrap_resamples":args.bootstrap,"raw_rows":len(raw),"groups":len(groups),"all_groups_have_30":not incomplete,"comparison_baseline":"brent_dekker","speedup_definition":"median(brent_dekker_time / candidate_time)"}
    (args.run_dir/"algorithm_analysis.json").write_text(json.dumps(summary,indent=2),encoding="utf-8");print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
