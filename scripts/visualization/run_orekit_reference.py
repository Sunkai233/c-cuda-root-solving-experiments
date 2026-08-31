#!/usr/bin/env python3
"""Run the Kepler benchmark through Orekit's production anomaly utility.

This worker is intentionally dependency-light.  On systems without a Java
installation it can be run from an ASCII-path virtual environment containing
``orekit-jpype[jdk4py]``.  The generated CSV files are consumed by the paper
figure renderer and are committed as frozen framework evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DEFAULT = ROOT / "paper_figures" / "domain_frameworks_v1" / "data"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def start_orekit():
    import orekit_jpype

    jvmpath = None
    try:
        import jdk4py

        java_home = Path(jdk4py.JAVA_HOME)
        os.environ.setdefault("JAVA_HOME", str(java_home))
        candidates = [
            java_home / "bin" / "server" / "jvm.dll",
            java_home / "lib" / "server" / "libjvm.so",
            java_home / "lib" / "server" / "libjvm.dylib",
        ]
        jvmpath = next((str(p) for p in candidates if p.exists()), None)
    except ImportError:
        pass
    orekit_jpype.initVM(
        jvmpath=jvmpath,
        vmargs="--enable-native-access=ALL-UNNAMED",
    )
    from org.orekit.orbits import KeplerianAnomalyUtility

    return KeplerianAnomalyUtility


def grid_eccentricities() -> list[float]:
    ordinary = [0.95 * i / 39 for i in range(40)]
    difficult = [1.0 - 10.0 ** (-x) for x in [2 + 7 * i / 31 for i in range(32)]]
    return sorted(set(ordinary + difficult))


def write_grid(out: Path, utility) -> dict:
    path = out / "kepler_orekit_grid.csv"
    es = grid_eccentricities()
    # Retain global [0, pi] coverage while resolving the high-condition corner
    # M -> 0 over nine decades.
    ms = sorted(set([0.0] + [math.pi * i / 119 for i in range(1, 120)]
                    + [10.0 ** (-10.0 + 9.0 * i / 59) for i in range(60)]))
    max_residual = 0.0
    max_condition = 0.0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["e", "M_rad", "E_rad", "residual", "condition_dE_dM", "x_over_a", "y_over_a"])
        for e in es:
            semiminor = math.sqrt(max(0.0, 1.0 - e * e))
            for M in ms:
                E = float(utility.ellipticMeanToEccentric(e, M))
                residual = abs(E - e * math.sin(E) - M)
                condition = 1.0 / (1.0 - e * math.cos(E))
                max_residual = max(max_residual, residual)
                max_condition = max(max_condition, condition)
                w.writerow([f"{e:.17g}", f"{M:.17g}", f"{E:.17g}", f"{residual:.17g}",
                            f"{condition:.17g}", f"{math.cos(E)-e:.17g}",
                            f"{semiminor*math.sin(E):.17g}"])
    return {
        "file": path.name,
        "rows": len(es) * len(ms),
        "n_e": len(es),
        "n_M": len(ms),
        "max_residual": max_residual,
        "max_condition": max_condition,
        "sha256": sha256(path),
    }


def write_reference_check(out: Path, utility) -> dict:
    source = ROOT / "references" / "ref_v3_20260824" / "kepler.csv"
    target = out / "kepler_orekit_reference_check.csv"
    max_error = 0.0
    max_residual = 0.0
    rows = 0
    with source.open(newline="", encoding="utf-8") as fi, target.open("w", newline="", encoding="utf-8") as fo:
        reader = csv.DictReader(fi)
        writer = csv.writer(fo)
        writer.writerow(["sample_id", "branch", "e", "M_rad", "orekit_E_rad", "mpmath_E_rad",
                         "absolute_error", "orekit_residual"])
        for row in reader:
            e = float(row["p0"])
            M = float(row["p1"])
            expected = float(row["root"])
            actual = float(utility.ellipticMeanToEccentric(e, M))
            error = abs(actual - expected)
            residual = abs(actual - e * math.sin(actual) - M)
            max_error = max(max_error, error)
            max_residual = max(max_residual, residual)
            rows += 1
            writer.writerow([row["sample_id"], row["branch"], f"{e:.17g}", f"{M:.17g}",
                             f"{actual:.17g}", f"{expected:.17g}", f"{error:.17g}", f"{residual:.17g}"])
    return {
        "file": target.name,
        "rows": rows,
        "max_absolute_error_vs_mpmath": max_error,
        "max_residual": max_residual,
        "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(source),
        "sha256": sha256(target),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    utility = start_orekit()
    manifest = {
        "framework": "Orekit KeplerianAnomalyUtility.ellipticMeanToEccentric",
        "orekit_jpype_version": importlib.metadata.version("orekit-jpype"),
        "equation": "E - e*sin(E) - M = 0, 0 <= e < 1, 0 <= M <= pi",
        "grid": write_grid(out, utility),
        "reference_check": write_reference_check(out, utility),
    }
    path = out / "kepler_orekit_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
