#!/usr/bin/env python3
"""Summarize the formal C17 CPU matrix and compare it with frozen GPU FP64.

Python is used only after timing.  CPU modes/builds and GPU results were run
sequentially, so all cross-group confidence intervals use independent bootstrap
rather than pretending that equal repetition numbers are paired observations.
"""
import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path
import numpy as np


def quantile(values, p):
    values = sorted(values)
    return values[int(p * (len(values) - 1))]


def independent_bootstrap(numerator, denominator, seed, draws=10000):
    rng = np.random.default_rng(seed)
    a, b = np.asarray(numerator), np.asarray(denominator)
    ai = rng.integers(0, len(a), size=(draws, len(a)))
    bi = rng.integers(0, len(b), size=(draws, len(b)))
    samples = np.median(a[ai], axis=1) / np.median(b[bi], axis=1)
    point = statistics.median(numerator) / statistics.median(denominator)
    return point, quantile(samples, .025), quantile(samples, .975)


def read_cpu(path):
    groups = defaultdict(list)
    nonfinite = defaultdict(int)
    checksums = defaultdict(set)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["domain"], int(row["n"]))
            groups[key].append(float(row["time_ms"]))
            nonfinite[key] += int(row["nonfinite"])
            checksums[key].add(row["checksum"])
    return groups, nonfinite, checksums


def read_gpu_fp64_e2e(path):
    groups = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["method"] == "fp64" and row["timing_kind"] == "e2e":
                groups[(row["domain"], int(row["n"]))].append(float(row["value_ms"]))
    return groups


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--gpu-repetitions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    inputs = {
        "strict_serial": args.run / "strict_serial.csv",
        "strict_simd": args.run / "strict_simd.csv",
        "strict_omp96": args.run / "strict_omp96.csv",
        "pgo_omp96": args.run / "pgo_omp96.csv",
    }
    data, nfs, sums = {}, {}, {}
    for label, path in inputs.items():
        data[label], nfs[label], sums[label] = read_cpu(path)

    summary = []
    for label in inputs:
        for (domain, n), values in sorted(data[label].items()):
            summary.append({
                "build_mode": label,
                "domain": domain,
                "n": n,
                "median_ms": statistics.median(values),
                "p05_ms": quantile(values, .05),
                "p95_ms": quantile(values, .95),
                "throughput_mroots_s": n / statistics.median(values) / 1000.0,
                "repetitions": len(values),
                "nonfinite_sum": nfs[label][(domain, n)],
                "checksum_variants": len(sums[label][(domain, n)]),
            })
    write_csv(args.out / "cpu_c17_summary.csv", list(summary[0]), summary)

    comparisons = []
    pairs = [
        ("strict_serial", "strict_simd", "serial_over_simd"),
        ("strict_serial", "strict_omp96", "serial_over_omp96"),
        ("strict_omp96", "pgo_omp96", "strict_omp96_over_pgo_omp96"),
    ]
    for left, right, name in pairs:
        for index, key in enumerate(sorted(set(data[left]) & set(data[right]))):
            point, low, high = independent_bootstrap(data[left][key], data[right][key],
                                                      20260824 + index + 1000 * len(name))
            comparisons.append({"comparison": name, "domain": key[0], "n": key[1],
                                "ratio": point, "ci95_low": low, "ci95_high": high,
                                "bootstrap_design": "independent_sequential_modes"})
    write_csv(args.out / "cpu_c17_mode_bootstrap.csv", list(comparisons[0]), comparisons)

    gpu = read_gpu_fp64_e2e(args.gpu_repetitions)
    cross = []
    for mode in ("strict_serial", "strict_omp96", "pgo_omp96"):
        for index, key in enumerate(sorted(set(data[mode]) & set(gpu))):
            point, low, high = independent_bootstrap(data[mode][key], gpu[key],
                                                      20260824 + index + 10000 * len(mode))
            cross.append({"cpu_mode": mode, "domain": key[0], "n": key[1],
                          "cpu_over_gpu_e2e": point, "ci95_low": low, "ci95_high": high,
                          "bootstrap_design": "independent"})
    write_csv(args.out / "cpu_gpu_fp64_bootstrap.csv", list(cross[0]), cross)
    print(f"wrote {len(summary)} summaries, {len(comparisons)} CPU comparisons, "
          f"and {len(cross)} CPU/GPU comparisons")


if __name__ == "__main__":
    main()
