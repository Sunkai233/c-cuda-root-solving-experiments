#!/usr/bin/env python3
"""Independent multi-step finite-difference check of implicit gradients.

Each perturbation re-solves the complete physical root problem at high
precision.  Python/mpmath is outside every timed C/CUDA path.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import mpmath as mp

PARAM_INDEX = {"bem": 0, "kepler": 1, "pv": 1, "cstr": 0, "peng_robinson": 0}
DEFAULT_STEPS = ("1e-2", "3e-3", "1e-3", "3e-4", "1e-4", "3e-5", "1e-5")


def bisect(f, lo, hi, steps=240):
    lo, hi = mp.mpf(lo), mp.mpf(hi)
    flo, fhi = f(lo), f(hi)
    if not (mp.isfinite(flo) and mp.isfinite(fhi)) or flo * fhi > 0:
        return None
    for _ in range(steps):
        mid = (lo + hi) / 2
        fm = f(mid)
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def all_roots(f, lo=0, hi=1, scans=512):
    roots, x0, f0 = [], mp.mpf(lo), f(mp.mpf(lo))
    for k in range(1, scans + 1):
        x1 = mp.mpf(lo) + (mp.mpf(hi) - lo) * k / scans
        f1 = f(x1)
        if mp.isfinite(f0) and mp.isfinite(f1) and f0 * f1 <= 0:
            r = bisect(f, x0, x1)
            if r is not None and all(abs(r-q) > mp.mpf("1e-35") for q in roots):
                roots.append(r)
        x0, f0 = x1, f1
    return roots


def solve(domain, p, branch):
    if domain == "bem":
        lam, sig, theta, cla, cd, _ = p
        def f(x):
            s, c = mp.sin(x), mp.cos(x); cl = cla*(x-theta)
            cn, ct = cl*c + cd*s, cl*s - cd*c
            return s-c/lam + sig*(cn+ct/lam)/(4*s)
        return bisect(f, mp.mpf("1e-4"), mp.pi/2-mp.mpf("1e-4")), 1
    if domain == "kepler":
        e, mean_anomaly = p[0], p[1]
        return bisect(lambda x: x-e*mp.sin(x)-mean_anomaly, 0, mp.pi), 1
    if domain == "pv":
        il, voltage, i0, a, rs, rsh = p
        def f(cur):
            return cur-il+i0*(mp.exp((voltage+cur*rs)/a)-1)+(voltage+cur*rs)/rsh
        return bisect(f, 0, il), 1
    if domain == "cstr":
        da, gamma, beta = p[:3]
        def f(x):
            rate = da*mp.exp(gamma*beta*x/(gamma+beta*x))
            return x-rate/(1+rate)
        roots = all_roots(f)
        if not roots:
            return None, 0
        return (roots[-1] if branch.startswith("high") else roots[0]), len(roots)
    if domain == "peng_robinson":
        A, B = p[:2]
        coeff = [1, -(1-B), A-3*B*B-2*B, -(A*B-B*B-B**3)]
        try:
            raw = mp.polyroots(coeff, maxsteps=400, error=False)
        except Exception:
            return None, 0
        roots = sorted(mp.re(z) for z in raw
                       if abs(mp.im(z)) < mp.mpf("1e-45") and mp.re(z) > B)
        if not roots:
            return None, 0
        return (roots[-1] if branch.startswith("vapor") else roots[0]), len(roots)
    raise ValueError(domain)


def check_one(task):
    domain, row, step_text, dps = task
    mp.mp.dps = dps
    p = [mp.mpf(row[f"p{k}"]) for k in range(6)]
    j = PARAM_INDEX[domain]
    reference_gradient = mp.mpf(row["gradient"])
    expected_roots = int(row["root_count"])
    records = []
    errors = []
    for rel_text in step_text:
        rel = mp.mpf(rel_text)
        h = abs(p[j])*rel
        pp, pm = list(p), list(p)
        pp[j] += h; pm[j] -= h
        rp, np = solve(domain, pp, row["branch"])
        rm, nm = solve(domain, pm, row["branch"])
        branch_stable = rp is not None and rm is not None and np == expected_roots and nm == expected_roots
        if branch_stable:
            fd = (rp-rm)/(2*h)
            abs_error = abs(fd-reference_gradient)
            rel_error = abs_error/max(abs(reference_gradient), mp.mpf("1e-40"))
            errors.append(float(rel_error))
            fd_text, ae_text, re_text = mp.nstr(fd, 25), mp.nstr(abs_error, 17), mp.nstr(rel_error, 17)
        else:
            fd_text = ae_text = re_text = "nan"
        records.append({"domain": domain, "sample_id": row["sample_id"],
                        "split": row["split"], "branch": row["branch"],
                        "parameter_index": j, "relative_step": rel_text,
                        "absolute_step": mp.nstr(h, 17), "fd_gradient": fd_text,
                        "reference_gradient": mp.nstr(reference_gradient, 25),
                        "absolute_error": ae_text, "relative_error": re_text,
                        "minus_root_count": nm, "plus_root_count": np,
                        "branch_stable": int(branch_stable)})
    finite = [r for r in records if r["branch_stable"]]
    best = min((float(r["relative_error"]) for r in finite), default=math.inf)
    sequence = [float(r["relative_error"]) for r in finite]
    decreases = sum(b < a for a, b in zip(sequence, sequence[1:]))
    sample = {"domain": domain, "sample_id": row["sample_id"],
              "branch": row["branch"], "valid_steps": len(finite),
              "best_relative_error": best,
              "convergence_observed": int(decreases >= 2)}
    return records, sample


def quantile(values, q):
    values = sorted(values)
    if not values:
        return math.nan
    x = (len(values)-1)*q; lo = int(x); hi = min(lo+1, len(values)-1); a = x-lo
    return values[lo]*(1-a)+values[hi]*a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--references", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", default="cal")
    ap.add_argument("--dps", type=int, default=80)
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--steps", nargs="*", default=list(DEFAULT_STEPS))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    tasks = []
    for domain in PARAM_INDEX:
        with (args.references/f"{domain}.csv").open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["split"] == args.split:
                    tasks.append((domain, row, tuple(args.steps), args.dps))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(check_one, tasks, chunksize=2))
    raw = [r for records, _ in results for r in records]
    samples = [s for _, s in results]
    fields = list(raw[0])
    with (args.out/"finite_difference_raw.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields); wr.writeheader(); wr.writerows(raw)
    with (args.out/"finite_difference_samples.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(samples[0])); wr.writeheader(); wr.writerows(samples)
    summary = []
    for domain in PARAM_INDEX:
        for rel in args.steps:
            rows = [r for r in raw if r["domain"] == domain and r["relative_step"] == rel]
            errs = [float(r["relative_error"]) for r in rows if r["branch_stable"]]
            summary.append({"domain": domain, "relative_step": rel, "n": len(rows),
                            "valid": len(errs), "branch_change_or_failure": len(rows)-len(errs),
                            "relative_error_median": quantile(errs, .5),
                            "relative_error_p95": quantile(errs, .95),
                            "relative_error_p99": quantile(errs, .99),
                            "relative_error_max": max(errs, default=math.nan)})
    with (args.out/"finite_difference_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(summary[0])); wr.writeheader(); wr.writerows(summary)
    manifest = {"split": args.split, "mpmath_dps": args.dps,
                "steps": args.steps, "samples": len(samples), "raw_rows": len(raw),
                "workers": args.workers,
                "samples_without_any_valid_step": sum(s["valid_steps"] == 0 for s in samples),
                "samples_without_observed_convergence": sum(not s["convergence_observed"] for s in samples)}
    (args.out/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
