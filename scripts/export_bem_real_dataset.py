#!/usr/bin/env python3
"""Export a compact, untimed-path binary dataset from OpenFAST nodal output."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

import numpy as np


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def group(names, suffix):
    x = [i for i, name in enumerate(names)
         if re.fullmatch(rf"AB[123]N\d{{3}}{suffix}", name)]
    if len(x) != 57:
        raise RuntimeError(f"{suffix}: expected 57, got {len(x)}")
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outb", type=Path, required=True)
    ap.add_argument("--openfast-io", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.openfast_io))
    from openfast_io.FAST_output_reader import FASTOutputFile

    args.out_dir.mkdir(parents=True, exist_ok=False)
    f = FASTOutputFile(str(args.outb))
    all_data = np.asarray(f.data)
    data = all_data[1:, :]
    previous = all_data[:-1, :]
    names = f.info["attribute_names"]
    if data.shape[0] != 48000:
        raise RuntimeError(f"expected 48000 noninitial steps, got {data.shape[0]}")

    # Original AeroDyn node numbers 2..18 on each blade. Node 1 is fixed by
    # hub loss, and node 19 is effectively fixed by tip loss.
    keep = np.asarray([b*19+n for b in range(3) for n in range(1, 18)])
    vx = data[:, np.asarray(group(names, "Vx"))[keep]]
    vy = data[:, np.asarray(group(names, "Vy"))[keep]]
    theta = np.deg2rad(data[:, np.asarray(group(names, "The"))[keep]])
    phi_ref = np.deg2rad(data[:, np.asarray(group(names, "Phi"))[keep]])
    phi_hint = np.deg2rad(previous[:, np.asarray(group(names, "Phi"))[keep]])
    geom = data[:, np.asarray(group(names, "Geo"))[keep]]
    arrays = [np.ascontiguousarray(x.reshape(-1), dtype="<f8")
              for x in (vx, vy, theta, phi_ref, phi_hint)]
    flags = np.ascontiguousarray((geom.reshape(-1) > 1e-12).astype(np.uint8))
    n = arrays[0].size
    if n != 48000*51 or any(x.size != n for x in arrays):
        raise RuntimeError("dataset shape mismatch")

    out = args.out_dir / "bem_real_f64_soa.bin"
    # 32-byte LE header: magic, version, records, f64 fields, nodes/step, steps.
    with out.open("wb") as fp:
        fp.write(struct.pack("<8sIQIII", b"BEMREAL2", 2, n, 5, 51, 48000))
        for x in arrays:
            x.tofile(fp)
        flags.tofile(fp)
    manifest = {
        "format": "BEMREAL2",
        "version": 2,
        "layout": "32-byte header, then SoA little-endian float64 Vx,Vy,ThetaRad,PhiRefRad,PhiHintPreviousStepRad, then uint8 GeomPhiFlag",
        "records": int(n), "steps": 48000, "ordinary_nodes_per_step": 51,
        "included_original_nodes": list(range(2, 19)), "blades": 3,
        "source_outb": str(args.outb), "source_outb_sha256": sha256(args.outb),
        "dataset": out.name, "dataset_bytes": out.stat().st_size,
        "dataset_sha256": sha256(out), "geometric_phi_flags": int(flags.sum()),
        "ranges": {
            "Vx": [float(vx.min()), float(vx.max())],
            "Vy": [float(vy.min()), float(vy.max())],
            "ThetaRad": [float(theta.min()), float(theta.max())],
            "PhiRefRad": [float(phi_ref.min()), float(phi_ref.max())],
            "PhiHintPreviousStepRad": [float(phi_hint.min()), float(phi_hint.max())],
        },
    }
    (args.out_dir/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
