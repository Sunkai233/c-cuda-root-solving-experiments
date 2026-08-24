#!/usr/bin/env python3
import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path
import numpy as np


def q(values, p):
    values = sorted(values)
    return values[int(p * (len(values) - 1))]


def load(path):
    groups = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            groups[(row["domain"], int(row["n"]))].append(float(row["time_ms"]))
    return groups


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("strict_csv", type=Path)
    parser.add_argument("fast_run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    strict = load(args.strict_csv)
    candidates = {"fast_math_lto": load(args.fast_run / "fast_omp96.csv"),
                  "strict_no_lto": load(args.fast_run / "strict_nolto_omp96.csv")}
    rows = []
    for ci, (candidate_name, candidate) in enumerate(candidates.items()):
        for index, key in enumerate(sorted(set(strict) & set(candidate))):
            left, right = strict[key], candidate[key]
            rng = np.random.default_rng(20260824 + index + 1000 * ci)
            la, ra = np.asarray(left), np.asarray(right)
            li = rng.integers(0, len(la), size=(10000, len(la)))
            ri = rng.integers(0, len(ra), size=(10000, len(ra)))
            boot = np.median(la[li], axis=1) / np.median(ra[ri], axis=1)
            rows.append({"candidate": candidate_name, "domain": key[0], "n": key[1],
                         "strict_lto_median_ms": statistics.median(strict[key]),
                         "candidate_median_ms": statistics.median(candidate[key]),
                         "strict_lto_over_candidate": statistics.median(left) / statistics.median(right),
                         "ci95_low": q(boot, .025), "ci95_high": q(boot, .975),
                         "bootstrap_design": "independent_sequential_runs"})
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "cpu_fast_performance_bootstrap.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} compilation comparisons; status={ (args.fast_run/'FAST_STATUS.txt').read_text().strip() }")


if __name__ == "__main__":
    main()
