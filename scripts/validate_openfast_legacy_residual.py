#!/usr/bin/env python3
"""Re-evaluate the OpenFAST legacy-BEM residual at exported reference roots.

This is intentionally independent of the future C/CUDA implementation.  It
uses the equations in BEMTUncoupled.f90 and exported Cl at Phi, so it audits
geometry/sign conventions before the airfoil interpolation path is added.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np


def read_blade(path: Path):
    rows = []
    started = False
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not started:
            if fields and fields[0] == "(m)":
                started = True
            continue
        if not fields or line.lstrip().startswith("!"):
            continue
        try:
            vals = [float(x) for x in fields[:6]]
            afid = int(fields[6])
        except (ValueError, IndexError):
            continue
        rows.append((*vals, afid))
        if len(rows) == 19:
            break
    if len(rows) != 19:
        raise RuntimeError(f"expected 19 blade nodes, got {len(rows)}")
    return np.asarray(rows, dtype=np.float64)


def channels(names, suffix):
    idx = [i for i, n in enumerate(names) if re.fullmatch(rf"AB[123]N\d{{3}}{suffix}", n)]
    if len(idx) != 57:
        raise RuntimeError(f"{suffix}: expected 57 channels, got {len(idx)}")
    return idx


def quantiles(x):
    x = np.abs(x[np.isfinite(x)])
    if x.size == 0:
        return {"count": 0, "median": None, "p95": None, "p99": None, "max": None}
    return {"count": int(x.size), "median": float(np.median(x)),
            "p95": float(np.quantile(x, .95)), "p99": float(np.quantile(x, .99)),
            "max": float(np.max(x))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outb", type=Path, required=True)
    ap.add_argument("--blade", type=Path, required=True)
    ap.add_argument("--openfast-io", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.openfast_io))
    from openfast_io.FAST_output_reader import FASTOutputFile

    f = FASTOutputFile(str(args.outb))
    data = np.asarray(f.data)[1:, :]  # exclude initialization output
    names = f.info["attribute_names"]
    vx = data[:, channels(names, "Vx")]
    vy = data[:, channels(names, "Vy")]
    phi = np.deg2rad(data[:, channels(names, "Phi")])
    cl = data[:, channels(names, "Cl")]

    blade = read_blade(args.blade)
    span, curve, sweep, chord = blade[:, 0], blade[:, 1], blade[:, 2], blade[:, 5]
    # Legacy AeroDyn projects the current blade position onto the rotor plane.
    # With blade structural DOFs disabled, transform the published local
    # curve/sweep/span coordinates through the fixed -2.5 degree precone.
    precone = np.deg2rad(-2.5)
    z_rotor = -(curve * np.sin(precone)) + (1.5 + span) * np.cos(precone)
    r_node = np.sqrt(sweep * sweep + z_rotor * z_rotor)
    # Tip/hub loss uses curvilinear zLocal, not projected rLocal.
    xyz = np.column_stack((curve, sweep, span))
    zlocal = np.empty(19)
    zlocal[0] = 1.5 + np.linalg.norm(xyz[0])
    zlocal[1:] = zlocal[0] + np.cumsum(np.linalg.norm(np.diff(xyz, axis=0), axis=1))
    ztip = zlocal[-1]
    r = np.tile(r_node, 3)[None, :]
    chord = np.tile(chord, 3)[None, :]
    fixed = np.tile(np.isclose(span, 0.0), 3)[None, :]

    s, c = np.sin(phi), np.cos(phi)
    z = np.tile(zlocal, 3)[None, :]
    tip_const = 3.0 * (ztip - z) / (2.0 * z)
    hub_const = 3.0 * (z - 1.5) / (2.0 * 1.5)
    abs_s = np.abs(s)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        ftip = (2.0 / np.pi) * np.arccos(np.minimum(1.0, np.exp(-tip_const / abs_s)))
        fhub = (2.0 / np.pi) * np.arccos(np.minimum(1.0, np.exp(-hub_const / abs_s)))
    f_loss = np.maximum(ftip * fhub, 1.0e-4)
    sigma = 3.0 * chord / (2.0 * np.pi * r)
    cn = cl * c                 # AIDrag=False
    ct = cl * s                 # TIDrag=False
    with np.errstate(divide="ignore", invalid="ignore"):
        k = sigma * cn / (4.0 * f_loss * s * s)
        kp = sigma * ct / (4.0 * f_loss * s * c)
    kp = np.where(vx < 0.0, -kp, kp)

    momentum = ((phi > 0.0) & (vx >= 0.0)) | ((phi < 0.0) & (vx < 0.0))
    a = np.empty_like(k)
    low = momentum & (k <= 2.0 / 3.0)
    a[low] = k[low] / (1.0 + k[low])
    high = momentum & ~low
    temp = 2.0 * f_loss * k
    g1 = temp - (10.0 / 9.0 - f_loss)
    g2 = temp - (4.0 / 3.0 - f_loss) * f_loss
    g3 = temp - (25.0 / 9.0 - 2.0 * f_loss)
    ah = np.where(np.abs(g3) < 1e-6, 1.0 - 0.5 / np.sqrt(g2),
                  (g1 - np.sqrt(np.abs(g2))) / g3)
    a[high] = ah[high]
    prop = ~momentum
    a[prop] = k[prop] / (k[prop] - 1.0)

    with np.errstate(divide="ignore", invalid="ignore"):
        residual = np.where(momentum,
                            s / (1.0 - a) - c / (vy / vx) * (1.0 - kp),
                            s * (1.0 - k) - c / (vy / vx) * (1.0 - kp))
    geo_idx = [i for i, n in enumerate(names)
               if re.fullmatch(r"AB[123]N\d{3}Geo", n)]
    if len(geo_idx) == 57:
        geom_phi_weight = data[:, geo_idx]
        geometric_fallback = np.abs(geom_phi_weight) > 1e-12
    else:
        geom_phi_weight = np.zeros_like(residual)
        geometric_fallback = np.zeros_like(residual, dtype=bool)
    # Match BEMTUncoupled.VelocityIsZero exactly: |v| < 0.001 m/s bypasses
    # induction and returns the special-case zero residual.
    base_numeric = (~fixed) & np.isfinite(residual) & (np.abs(vx) >= 1e-3) & (np.abs(vy) >= 1e-3)
    valid = base_numeric & ~geometric_fallback
    by_node = []
    for node in range(19):
        sel = np.zeros_like(valid)
        sel[:, node] = sel[:, 19 + node] = sel[:, 38 + node] = True
        by_node.append({"node": node + 1, **quantiles(residual[valid & sel])})
    result = {
        "source_outb": args.outb.name,
        "evaluated_noninitial_node_states": int(data.shape[0] * 57),
        "fixed_hub_states_excluded": int(data.shape[0] * 3),
        "geometric_phi_fallback_states": int((base_numeric & geometric_fallback).sum()),
        "geom_phi_weight_abs": quantiles(
            geom_phi_weight[np.broadcast_to(~fixed, geom_phi_weight.shape)]),
        "finite_nonfixed_residuals": int(valid.sum()),
        "abs_residual": quantiles(residual[valid]),
        "by_node": by_node,
    }
    bem_idx = [i for i, n in enumerate(names)
               if re.fullmatch(r"AB[123]N\d{3}BEM", n)]
    if len(bem_idx) == 4 * 57:
        chunks = [data[:, bem_idx[q*57:(q+1)*57]] for q in range(4)]
        # AeroDyn sorts nodal-output enums rather than preserving request-file
        # order, while the fixed-width binary labels collapse all four names to
        # "BEM".  Identify the chunks empirically and record the full matrix.
        candidates = {"k": k, "kp": kp, "F": f_loss, "CT": ct}

        def median_relative(calc, ref):
            mask = np.isfinite(calc) & np.isfinite(ref)
            scale = np.maximum(np.abs(ref[mask]), 1e-12)
            return float(np.median(np.abs(calc[mask]-ref[mask]) / scale))

        matching = {name: [median_relative(calc, chunk) for chunk in chunks]
                    for name, calc in candidates.items()}
        chosen = {name: int(np.argmin(vals)) for name, vals in matching.items()}
        k_ref, kp_ref, f_ref, ct_ref = (chunks[chosen[x]] for x in ("k", "kp", "F", "CT"))

        def compare(calc, ref):
            mask = np.isfinite(calc) & np.isfinite(ref)
            scale = np.maximum(np.abs(ref), 1e-12)
            return {"absolute": quantiles((calc-ref)[mask]),
                    "relative": quantiles(((calc-ref)/scale)[mask])}

        result["internal_diagnostic_comparison"] = {
            "chunk_matching_median_relative": matching,
            "chosen_chunk_zero_based": chosen,
            "k": compare(k, k_ref),
            "kp": compare(kp, kp_ref),
            "F": compare(f_loss, f_ref),
            "ct": compare(ct, ct_ref),
        }
        with np.errstate(divide="ignore", invalid="ignore"):
            implied_r = 3.0 * chord * cn / (2.0*np.pi * 4.0*f_ref*s*s*k_ref)
        implied_rows = []
        for node in range(19):
            cols = [node, 19+node, 38+node]
            vals = implied_r[:, cols].reshape(-1)
            kvals = k_ref[:, cols].reshape(-1)
            vals = vals[np.isfinite(vals) & (np.abs(kvals) > 1e-8) & (vals > 0.0)]
            implied_rows.append({
                "node": node+1, "candidate_r": float(r_node[node]),
                "count": int(vals.size),
                "median": float(np.median(vals)) if vals.size else None,
                "min": float(np.min(vals)) if vals.size else None,
                "max": float(np.max(vals)) if vals.size else None,
                "std": float(np.std(vals)) if vals.size else None,
            })
        result["internal_diagnostic_comparison"]["implied_r_by_node"] = implied_rows
        ai = np.empty_like(k_ref)
        lowi = momentum & (k_ref <= 2.0/3.0)
        ai[lowi] = k_ref[lowi] / (1.0 + k_ref[lowi])
        highi = momentum & ~lowi
        tempi = 2.0*f_ref*k_ref
        g1i = tempi - (10.0/9.0-f_ref)
        g2i = tempi - (4.0/3.0-f_ref)*f_ref
        g3i = tempi - (25.0/9.0-2.0*f_ref)
        with np.errstate(invalid="ignore", divide="ignore"):
            ahi = np.where(np.abs(g3i) < 1e-6, 1.0-0.5/np.sqrt(g2i),
                           (g1i-np.sqrt(np.abs(g2i)))/g3i)
        ai[highi] = ahi[highi]
        ai[prop] = k_ref[prop] / (k_ref[prop]-1.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            ri = np.where(momentum,
                          s/(1.0-ai)-c/(vy/vx)*(1.0-kp_ref),
                          s*(1.0-k_ref)-c/(vy/vx)*(1.0-kp_ref))
        result["internal_diagnostic_comparison"]["residual_from_exported_k_kp_F"] = quantiles(ri[valid])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["abs_residual"], indent=2))


if __name__ == "__main__":
    main()
