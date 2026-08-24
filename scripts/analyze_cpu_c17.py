#!/usr/bin/env python3
"""Summarize the formal C17 CPU matrix and compare it with frozen GPU FP64.

Python is used only after timing.  Within-CPU ratios use matching repetition
indices; CPU/GPU ratios use independent bootstrap because the devices were run
at different times and are not a paired experiment.
"""
import argparse
import csv
import random
import statistics
from collections import defaultdict
from pathlib import Path


def quantile(values, p):
    values = sorted(values)
    return values[int(p * (len(values) - 1))]


def paired_bootstrap(numerator, denominator, seed, draws=10000):
    ratios = [x / y for x, y in zip(numerator, denominator)]
    rng = random.Random(seed)
    n = len(ratios)
    samples = [statistics.median(ratios[rng.randrange(n)] for _ in range(n))
               for _ in range(draws)]
    return statistics.median(ratios), quantile(samples, .025), quantile(samples, .975)


def independent_bootstrap(numerator, denominator, seed, draws=10000):
    rng = random.Random(seed)
    nn, nd = len(numerator), len(denominator)
    samples = []
    for _ in range(draws):
        a = statistics.median(numerator[rng.randrange(nn)] for _ in range(nn))
        b = statistics.median(denominator[rng.randrange(nd)] for _ in range(nd))
        samples.append(a / b)
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
            point, low, high = paired_bootstrap(data[left][key], data[right][key],
                                                 20260824 + index + 1000 * len(name))
            comparisons.append({"comparison": name, "domain": key[0], "n": key[1],
                                "ratio": point, "ci95_low": low, "ci95_high": high})
    write_csv(args.out / "cpu_c17_paired_bootstrap.csv", list(comparisons[0]), comparisons)

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
