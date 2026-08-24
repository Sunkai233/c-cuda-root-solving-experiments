#!/usr/bin/env python3
import argparse,csv,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np

def wilson(k,n,z=1.959963984540054):
    if not n:return (float("nan"),float("nan"))
    p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0,c-h),min(1,c+h)
p=argparse.ArgumentParser();p.add_argument("run",type=Path);a=p.parse_args()
raw=a.run/"validation_test_raw.csv";groups=defaultdict(list)
with raw.open(newline="",encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["method"]!="adaptive_frozen_v2":continue
        groups[(r["domain"],"all")].append(r);groups[(r["domain"],r["branch"])].append(r)
qs=[.5,.9,.95,.99,.999,1.0];out=[]
for (domain,branch),rows in sorted(groups.items()):
    re=np.array([float(r["root_abs_error"]) for r in rows]);ge=np.array([float(r["gradient_relative_error"]) for r in rows]);rv=np.array([float(r["residual_abs"]) for r in rows])
    margin=1e-4 if domain=="peng_robinson" else 2e-6
    failures=np.logical_or.reduce((~np.isfinite(re),re>1e-7,~np.isfinite(ge),ge>margin))
    lo,hi=wilson(int(failures.sum()),len(rows));rec={"domain":domain,"branch":branch,"n":len(rows),"failures":int(failures.sum()),"failure_wilson95_low":lo,"failure_wilson95_high":hi,"corrections":sum(int(r["precision_path"])==3 for r in rows)}
    for name,x in (("root_abs",re),("gradient_rel",ge),("residual_abs",rv)):
        for q in qs:rec[f"{name}_{'max' if q==1 else 'p'+str(q*100).rstrip('0').rstrip('.').replace('.','_')}"]=float(np.quantile(x,q,method="nearest"))
    out.append(rec)
(a.run/"frozen_v2_analysis.json").write_text(json.dumps({"method":"adaptive_frozen_v2","root_margin":1e-7,"gradient_margin_main":2e-6,"gradient_margin_pr":1e-4,"groups":out},indent=2),encoding="utf-8")
with (a.run/"frozen_v2_by_branch.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print(json.dumps({"groups":len(out),"total_failures_all_groups":sum(x["failures"] for x in out if x["branch"]=="all")},indent=2))
