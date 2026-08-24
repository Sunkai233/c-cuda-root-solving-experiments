#!/usr/bin/env python3
"""Audit a full OpenFAST NREL-5MW nodal BEM output file."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outb", type=Path, required=True)
    ap.add_argument("--openfast-io", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.openfast_io))
    from openfast_io.FAST_output_reader import FASTOutputFile

    args.out.mkdir(parents=True, exist_ok=False)
    f = FASTOutputFile(str(args.outb))
    data = np.asarray(f.data)
    names = f.info["attribute_names"]
    units = f.info["attribute_units"]
    if data.shape[1] != len(names):
        raise RuntimeError("channel metadata mismatch")
    # OpenFAST's binary channel labels are fixed-width; Alpha/Theta are stored
    # with three-character suffixes.
    wanted = {"Vx": "Vx", "Vy": "Vy", "Phi": "Phi", "Alpha": "Alp", "Theta": "The",
              "AxI": "AxI", "TnI": "TnI", "Cl": "Cl", "Cd": "Cd",
              "Cx": "Cx", "Cy": "Cy", "Fl": "Fl", "Fd": "Fd"}
    groups = {}
    channel_rows = []
    for label, suffix in wanted.items():
        idx = [i for i, n in enumerate(names)
               if re.fullmatch(rf"AB[123]N\d{{3}}{suffix}", n)]
        groups[label] = idx
        for i in idx:
            x = data[:, i]
            channel_rows.append({"channel": names[i], "unit": units[i],
                                 "finite": int(np.isfinite(x).sum()),
                                 "nonfinite": int((~np.isfinite(x)).sum()),
                                 "min": float(np.nanmin(x)),
                                 "median": float(np.nanmedian(x)),
                                 "max": float(np.nanmax(x))})
    time = data[:, 0]
    dt = np.diff(time)
    summary = {
        "file": args.outb.name,
        "rows_including_initial": int(data.shape[0]),
        "time_steps_excluding_initial": int(data.shape[0]-1),
        "channels": int(data.shape[1]),
        "time_start": float(time[0]), "time_end": float(time[-1]),
        "dt_min": float(dt.min()), "dt_max": float(dt.max()),
        "blade_node_channels": {k: len(v) for k, v in groups.items()},
        "node_states_excluding_initial": int((data.shape[0]-1)*len(groups["Phi"])),
        "fixed_induction_states_excluding_initial": int((data.shape[0]-1)*6),
        "ordinary_root_instances_excluding_initial": int((data.shape[0]-1)*51),
        "root_outputs_including_initial": int(data.shape[0]*len(groups["Phi"])),
        "nodal_nonfinite": int(sum(r["nonfinite"] for r in channel_rows)),
    }
    # Independent consistency check for the directly exported physical input
    # Theta: AeroDyn defines Alpha = wrap(Phi - Theta) in degrees.
    phi = data[:, groups["Phi"]]
    alpha = data[:, groups["Alpha"]]
    theta = data[:, groups["Theta"]]
    alpha_from_states = (phi - theta + 180.0) % 360.0 - 180.0
    theta_identity_error = (alpha_from_states - alpha + 180.0) % 360.0 - 180.0
    summary["theta_identity_max_abs_deg"] = float(np.max(np.abs(theta_identity_error)))
    # 778 is the frozen base schema.  Benchmark cases may append diagnostic
    # nodal fields (BEM k/kp/F/CT) without invalidating the required schema.
    expected = data.shape[0] == 48001 and data.shape[1] >= 778 and all(
        len(groups[k]) == 57 for k in wanted)
    summary["shape_and_channel_audit_pass"] = bool(
        expected and summary["theta_identity_max_abs_deg"] < 1e-3)
    summary["finite_audit_pass"] = summary["nodal_nonfinite"] == 0
    (args.out/"openfast_bem_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    with (args.out/"openfast_bem_channel_stats.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(channel_rows[0])); wr.writeheader(); wr.writerows(channel_rows)
    print(json.dumps(summary, indent=2))
    if not (summary["shape_and_channel_audit_pass"] and summary["finite_audit_pass"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
