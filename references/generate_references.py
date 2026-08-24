#!/usr/bin/env python3
"""Generate append-only >=100-bit reference roots and implicit gradients.

Python is used only before timed C/CUDA execution. Decimal roots retain the
high-precision oracle; float parameters are frozen in the same CSV.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import mpmath as mp

FIELDS = ["domain", "sample_id", "split", "branch", "p0", "p1", "p2",
          "p3", "p4", "p5", "root", "gradient", "residual", "root_count",
          "status"]


def bisect(f, lo, hi, steps=220):
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


def all_roots(f, lo, hi, scans=512):
    roots, x0, f0 = [], mp.mpf(lo), f(mp.mpf(lo))
    for k in range(1, scans + 1):
        x1 = mp.mpf(lo) + (mp.mpf(hi) - lo) * k / scans
        f1 = f(x1)
        if mp.isfinite(f0) and mp.isfinite(f1) and f0 * f1 <= 0:
            r = bisect(f, x0, x1)
            if r is not None and all(abs(r - q) > mp.mpf("1e-35") for q in roots):
                roots.append(r)
        x0, f0 = x1, f1
    return roots


def split_for(i):
    r = i % 10
    return "dev" if r < 6 else ("cal" if r < 8 else "test")


def fmt(x):
    return mp.nstr(x, 55)


def bem(rng):
    lam = mp.mpf(1 + 13 * rng.random())
    sig = mp.mpf(.02 + .18 * rng.random())
    theta = mp.radians(-2 + 18 * rng.random())
    cla, cd = 2 * mp.pi, mp.mpf(.006 + .014 * rng.random())

    def fd(x):
        s, co = mp.sin(x), mp.cos(x); cl = cla * (x - theta)
        cn, ct = cl * co + cd * s, cl * s - cd * co
        return s - co / lam + sig * (cn + ct / lam) / (4 * s)

    lo, hi = mp.mpf("1e-4"), mp.pi / 2 - mp.mpf("1e-4")
    root = bisect(fd, lo, hi)
    if root is None or not (mp.mpf("0.02") < root < mp.mpf("1.55")):
        return None
    x = root; s, co = mp.sin(x), mp.cos(x); cl = cla * (x - theta)
    cn, ct = cl * co + cd * s, cl * s - cd * co
    cnp = cla * co - cl * s + cd * co
    ctp = cla * s + cl * co + cd * s
    q, qp = cn + ct / lam, cnp + ctp / lam
    fx = co + s / lam + sig * (qp * s - q * co) / (4 * s * s)
    flam = co / (lam * lam) - sig * ct / (4 * s * lam * lam)
    return [lam, sig, theta, cla, cd, 0], root, -flam / fx, fd(root), 1, "smooth"


def kepler(rng, i):
    if i % 4 == 0:
        e = 1 - mp.power(10, -7 - 4 * rng.random())
        M = mp.power(10, -8 + 6 * rng.random())
        branch = "difficult"
    elif i % 4 == 1:
        e, M, branch = mp.mpf(.9 + .09 * rng.random()), mp.pi * rng.random(), "high_e"
    else:
        e, M, branch = mp.mpf(.9 * rng.random()), mp.pi * rng.random(), "ordinary"
    f = lambda x: x - e * mp.sin(x) - M
    root = bisect(f, 0, mp.pi)
    fx = 1 - e * mp.cos(root)
    return [e, M, 0, 0, 0, 0], root, 1 / fx, f(root), 1, branch


def pv(rng, i):
    il = mp.mpf(1 + 11 * rng.random())
    i0 = mp.power(10, -12 + 5 * rng.random())
    a = mp.mpf(1 + 1.4 * rng.random())
    rs = mp.mpf(.02 + .78 * rng.random())
    rsh = mp.power(10, 2 + 1.5 * rng.random())
    voc_f = lambda v: -il + i0 * (mp.exp(v / a) - 1) + v / rsh
    voc = bisect(voc_f, 0, a * mp.log(il / i0 + 1) * mp.mpf("1.2"))
    frac = mp.mpf(rng.random()) ** 2
    v = mp.mpf("0.995") * frac * voc
    f = lambda cur: cur - il + i0 * (mp.exp((v + cur * rs) / a) - 1) + (v + cur * rs) / rsh
    root = bisect(f, 0, il)
    z = (v + root * rs) / a; ez = mp.exp(z)
    fx = 1 + i0 * ez * rs / a + rs / rsh
    fv = i0 * ez / a + 1 / rsh
    branch = "short_circuit" if frac < .05 else ("open_circuit" if frac > .9 else "interior")
    return [il, v, i0, a, rs, rsh], root, -fv / fx, f(root), 1, branch


def cstr(rng, i):
    # Broad deterministic search retains both one- and three-root cases.
    target_triple = (i % 3 == 0)
    for _ in range(200):
        if target_triple:
            da = mp.power(10, -6 + 4.8 * rng.random())
            gamma = mp.mpf(8 + 92 * rng.random())
            beta = mp.mpf(8 + 92 * rng.random())
        else:
            da = mp.power(10, -3 + 4 * rng.random())
            gamma = mp.mpf(2 + 28 * rng.random())
            beta = mp.mpf(.05 + 5 * rng.random())
        def f(x):
            r = da * mp.exp(gamma * beta * x / (gamma + beta * x))
            return x - r / (1 + r)
        roots = all_roots(f, 0, 1, 384)
        if roots and ((target_triple and len(roots) == 3) or (not target_triple and len(roots) == 1)):
            want_high = bool(i & 1)
            root = roots[-1] if want_high else roots[0]
            den = gamma + beta * root
            r = da * mp.exp(gamma * beta * root / den)
            fx = 1 - r * gamma * gamma * beta / (den * den * (1 + r) ** 2)
            fda = -(r / da) / (1 + r) ** 2
            branch = ("high" if want_high else "low") + ("_triple" if len(roots) == 3 else "_single")
            return [da, gamma, beta, 0, 0, 0], root, -fda / fx, f(root), len(roots), branch
    return None


def peng_robinson(rng, i):
    # Standard PR compressibility cubic in Z, parameterized by A and B.
    target_triple = (i % 3 == 0)
    for _ in range(200):
        if target_triple:
            A = mp.power(10, -3 + 2.6 * rng.random())
            B = mp.power(10, -4 + 2.7 * rng.random())
        else:
            A = mp.mpf(.05 + 1.2 * rng.random())
            B = mp.mpf(.01 + .24 * rng.random())
        coeff = [1, -(1 - B), A - 3 * B * B - 2 * B, -(A * B - B * B - B ** 3)]
        try:
            raw = mp.polyroots(coeff, maxsteps=300, error=False)
        except Exception:
            continue
        roots = sorted([mp.re(z) for z in raw if abs(mp.im(z)) < mp.mpf("1e-45") and mp.re(z) > B])
        if not roots or (target_triple and len(roots) != 3) or (not target_triple and len(roots) != 1):
            continue
        root = roots[-1] if (i & 1) else roots[0]
        f = lambda z: z**3 - (1-B)*z**2 + (A-3*B*B-2*B)*z - (A*B-B*B-B**3)
        fx = 3*root**2 - 2*(1-B)*root + A-3*B*B-2*B
        fA = root - B
        phase = "vapor" if i & 1 else "liquid"
        return [A, B, 0, 0, 0, 0], root, -fA / fx, f(root), len(roots), phase + ("_triple" if len(roots) == 3 else "_single")
    return None


GENERATORS = {"bem": bem, "kepler": kepler, "pv": pv, "cstr": cstr,
              "peng_robinson": peng_robinson}


def generate_domain(domain, per_domain, seed, dps, out):
    mp.mp.dps = dps
    di = list(GENERATORS).index(domain)
    gen = GENERATORS[domain]
    path = Path(out) / f"{domain}.csv"
    rng = random.Random(seed + di * 1000003)
    counts = Counter()
    with path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS); wr.writeheader()
        made, attempts = 0, 0
        while made < per_domain:
            result = gen(rng, made) if domain != "bem" else gen(rng)
            attempts += 1
            if result is None:
                if attempts > per_domain * 100: raise RuntimeError(f"generation stalled: {domain}")
                continue
            params, root, grad, resid, nroot, branch = result
            row = {"domain": domain, "sample_id": f"{domain}_{made:07d}",
                   "split": split_for(made), "branch": branch,
                   **{f"p{k}": fmt(params[k]) for k in range(6)},
                   "root": fmt(root), "gradient": fmt(grad),
                   "residual": fmt(abs(resid)), "root_count": nroot,
                   "status": "ROOT_OK"}
            wr.writerow(row); counts[(domain, row["split"], branch)] += 1; made += 1
    return domain, path.name, hashlib.sha256(path.read_bytes()).hexdigest(), dict(counts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-domain", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20260824)
    ap.add_argument("--dps", type=int, default=55)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    mp.mp.dps = args.dps
    args.out.mkdir(parents=True, exist_ok=False)
    counts, hashes = Counter(), {}
    jobs = []
    with ProcessPoolExecutor(max_workers=len(GENERATORS)) as pool:
        for domain in GENERATORS:
            jobs.append(pool.submit(generate_domain, domain, args.per_domain,
                                    args.seed, args.dps, str(args.out)))
        for job in as_completed(jobs):
            domain, name, digest, domain_counts = job.result()
            hashes[name] = digest
            counts.update(domain_counts)
            print(f"completed {domain}", flush=True)
    hashes = dict(sorted(hashes.items()))
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "generator": Path(__file__).name, "seed": args.seed,
                "mpmath_dps": args.dps, "minimum_bits": math.floor(args.dps*math.log2(10)),
                "per_domain": args.per_domain, "files_sha256": hashes,
                "counts": {"|".join(map(str,k)): v for k,v in sorted(counts.items())}}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
