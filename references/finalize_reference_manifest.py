#!/usr/bin/env python3
"""Finalize a fully generated reference directory after an interrupted parent."""
import argparse,csv,hashlib,json,math
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument("--dir",type=Path,required=True);p.add_argument("--seed",type=int,required=True);p.add_argument("--dps",type=int,required=True);p.add_argument("--per-domain",type=int,required=True);a=p.parse_args()
counts=Counter();hashes={}
for domain in ("bem","kepler","pv","cstr","peng_robinson"):
    f=a.dir/f"{domain}.csv"
    if not f.exists() or f.stat().st_size==0: raise SystemExit(f"missing {f}")
    with f.open(newline="",encoding="utf-8") as h:
        rows=list(csv.DictReader(h))
    if len(rows)!=a.per_domain: raise SystemExit(f"{f}: {len(rows)} rows")
    for r in rows: counts[(domain,r["split"],r["branch"])]+=1
    hashes[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
m={"created_utc":datetime.now(timezone.utc).isoformat(),"generator":"generate_references.py","finalizer":Path(__file__).name,"seed":a.seed,"mpmath_dps":a.dps,"minimum_bits":math.floor(a.dps*math.log2(10)),"per_domain":a.per_domain,"files_sha256":dict(sorted(hashes.items())),"counts":{"|".join(k):v for k,v in sorted(counts.items())}}
(a.dir/"manifest.json").write_text(json.dumps(m,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(m,indent=2,ensure_ascii=False))
