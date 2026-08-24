#!/usr/bin/env python3
"""Independent hash, residual, and multi-step finite-difference verification."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import mpmath as mp

from generate_references import all_roots, bisect


def residual(domain, p, x):
    if domain == "bem":
        lam, sig, theta, cla, cd = p[:5]
        s, co = mp.sin(x), mp.cos(x); cl = cla * (x - theta)
        cn, ct = cl * co + cd * s, cl * s - cd * co
        return s - co / lam + sig * (cn + ct / lam) / (4 * s)
    if domain == "kepler":
        return x - p[0] * mp.sin(x) - p[1]
    if domain == "pv":
        il, v, i0, a, rs, rsh = p
        return x - il + i0 * (mp.exp((v + x * rs) / a) - 1) + (v + x * rs) / rsh
    if domain == "cstr":
        da, gamma, beta = p[:3]
        r = da * mp.exp(gamma * beta * x / (gamma + beta * x))
        return x - r / (1 + r)
    A, B = p[:2]
    return x**3 - (1-B)*x**2 + (A-3*B*B-2*B)*x - (A*B-B*B-B**3)


def solve_near(domain, p, target):
    f = lambda x: residual(domain, p, x)
    if domain == "bem": roots = [bisect(f, mp.mpf("1e-4"), mp.pi/2-mp.mpf("1e-4"))]
    elif domain == "kepler": roots = [bisect(f, 0, mp.pi)]
    elif domain == "pv": roots = [bisect(f, 0, p[0])]
    elif domain == "cstr": roots = all_roots(f, 0, 1, 768)
    else:
        A, B = p[:2]
        coeff = [1, -(1-B), A-3*B*B-2*B, -(A*B-B*B-B**3)]
        roots = [mp.re(z) for z in mp.polyroots(coeff, maxsteps=500)
                 if abs(mp.im(z)) < mp.mpf("1e-60") and mp.re(z) > B]
    roots = [x for x in roots if x is not None]
    if not roots: raise RuntimeError(f"no perturbed root for {domain}")
    return min(roots, key=lambda x: abs(x-target))


def q(values, frac):
    s = sorted(values); return s[min(len(s)-1, int(frac*(len(s)-1)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", type=Path)
    ap.add_argument("--dps", type=int, default=80)
    ap.add_argument("--fd-per-domain", type=int, default=25)
    args = ap.parse_args(); mp.mp.dps = args.dps
    manifest = json.loads((args.directory / "manifest.json").read_text(encoding="utf-8"))
    hash_ok, residuals, stored_residuals, rows_by_domain = True, [], [], {}
    split_counts = Counter()
    for name, expected in manifest["files_sha256"].items():
        path = args.directory / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        hash_ok &= actual == expected
        domain = path.stem; rows = list(csv.DictReader(path.open(encoding="utf-8")))
        rows_by_domain[domain] = rows
        for row in rows:
            p = [mp.mpf(row[f"p{k}"]) for k in range(6)]; root = mp.mpf(row["root"])
            residuals.append(float(abs(residual(domain, p, root))))
            stored_residuals.append(float(mp.mpf(row["residual"])))
            split_counts[(domain, row["split"])] += 1
    primary = {"bem": 0, "kepler": 1, "pv": 1, "cstr": 0, "peng_robinson": 0}
    fd_errors, fd_counts = {}, {}
    for domain, rows in rows_by_domain.items():
        chosen = [r for r in rows if r["split"] == "dev"][:args.fd_per_domain]
        errs = []
        for row in chosen:
            p = [mp.mpf(row[f"p{k}"]) for k in range(6)]
            target, grad = mp.mpf(row["root"]), mp.mpf(row["gradient"])
            j = primary[domain]
            estimates = []
            for exponent in (16, 18, 20):
                h = max(abs(p[j]), mp.mpf(1)) * mp.power(10, -exponent)
                pp, pm = list(p), list(p); pp[j] += h; pm[j] -= h
                rp, rm = solve_near(domain, pp, target), solve_near(domain, pm, target)
                estimates.append((rp-rm)/(2*h))
            # Require the two finest estimates to agree; otherwise mark branch/FD risk.
            if abs(estimates[-1]-estimates[-2]) <= mp.mpf("1e-10")*max(abs(estimates[-1]), 1):
                errs.append(float(abs(estimates[-1]-grad)/max(abs(grad), mp.mpf("1e-80"))))
        fd_errors[domain] = {"median": q(errs,.5), "p95": q(errs,.95), "max": max(errs)} if errs else {}
        fd_counts[domain] = {"accepted": len(errs), "attempted": len(chosen)}
    report = {
        "reference_directory": args.directory.name,
        "verification_dps": args.dps,
        "hashes_match_manifest": hash_ok,
        "rows_total": sum(len(v) for v in rows_by_domain.values()),
        "split_counts": {"|".join(k): v for k,v in sorted(split_counts.items())},
        "recomputed_residual": {"median": q(residuals,.5), "p99": q(residuals,.99), "max": max(residuals)},
        "stored_residual_max": max(stored_residuals),
        "finite_difference_relative_error": fd_errors,
        "finite_difference_counts": fd_counts,
        "pass": bool(hash_ok and max(residuals) < 1e-45 and
                     all(v and v["max"] < 1e-8 for v in fd_errors.values()))
    }
    (args.directory / "verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__": main()
