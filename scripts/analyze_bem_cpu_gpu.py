#!/usr/bin/env python3
import argparse
import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path


def q(values, p):
    values = sorted(values); return values[int(p * (len(values) - 1))]


def independent(a, b, seed):
    rng = random.Random(seed); na, nb = len(a), len(b); boot = []
    for _ in range(10000):
        ma = statistics.median(a[rng.randrange(na)] for _ in range(na))
        mb = statistics.median(b[rng.randrange(nb)] for _ in range(nb))
        boot.append(ma / mb)
    return statistics.median(a) / statistics.median(b), q(boot, .025), q(boot, .975)


def load_cpu(path):
    groups = defaultdict(list); failures = defaultdict(int); checksums = defaultdict(set)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            groups[row["algorithm"]].append(float(row["time_ms"]))
            failures[row["algorithm"]] += int(row["failures"])
            checksums[row["algorithm"]].add(row["checksum"])
    return groups, failures, checksums


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cpu_run", type=Path)
    parser.add_argument("gpu_run", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    serial, sf, sc = load_cpu(args.cpu_run / "serial.csv")
    omp, of, oc = load_cpu(args.cpu_run / "omp96.csv")
    ids = {"bisection": 0, "brent": 1, "illinois": 2, "adaptive_compacted": 4}
    rows = []
    for index, name in enumerate(ids):
        gpu = json.loads((args.gpu_run / f"performance_alg{ids[name]}.json").read_text())
        serial_over_omp = independent(serial[name], omp[name], 20260824 + index)
        omp_over_gpu_kernel = independent(omp[name], gpu["kernel_times_ms"], 20261824 + index)
        omp_over_gpu_e2e = independent(omp[name], gpu["end_to_end_times_ms"], 20262824 + index)
        serial_over_gpu_e2e = independent(serial[name], gpu["end_to_end_times_ms"], 20263824 + index)
        rows.append({
            "algorithm": name, "records": gpu["records"],
            "cpu_serial_median_ms": statistics.median(serial[name]),
            "cpu_omp96_median_ms": statistics.median(omp[name]),
            "gpu_kernel_median_ms": statistics.median(gpu["kernel_times_ms"]),
            "gpu_e2e_median_ms": statistics.median(gpu["end_to_end_times_ms"]),
            "cpu_serial_over_omp96": serial_over_omp[0],
            "cpu_serial_over_omp96_ci_low": serial_over_omp[1],
            "cpu_serial_over_omp96_ci_high": serial_over_omp[2],
            "cpu_omp96_over_gpu_kernel": omp_over_gpu_kernel[0],
            "cpu_omp96_over_gpu_kernel_ci_low": omp_over_gpu_kernel[1],
            "cpu_omp96_over_gpu_kernel_ci_high": omp_over_gpu_kernel[2],
            "cpu_omp96_over_gpu_e2e": omp_over_gpu_e2e[0],
            "cpu_omp96_over_gpu_e2e_ci_low": omp_over_gpu_e2e[1],
            "cpu_omp96_over_gpu_e2e_ci_high": omp_over_gpu_e2e[2],
            "cpu_serial_over_gpu_e2e": serial_over_gpu_e2e[0],
            "cpu_serial_over_gpu_e2e_ci_low": serial_over_gpu_e2e[1],
            "cpu_serial_over_gpu_e2e_ci_high": serial_over_gpu_e2e[2],
            "cpu_failure_sum": sf[name] + of[name],
            "serial_checksum_variants": len(sc[name]), "omp_checksum_variants": len(oc[name]),
            "bootstrap_design_cpu_modes": "independent_sequential_modes",
            "bootstrap_design_cpu_gpu": "independent",
        })
    path = args.out / "bem_cpu_gpu_bootstrap.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
