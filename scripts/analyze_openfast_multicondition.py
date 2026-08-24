#!/usr/bin/env python3
import argparse
import csv
import json
import random
import statistics
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


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    conditions = ["8mps_C_seed27183", "16mps_A_seed39107"]
    methods = {0: "bisection", 1: "brent", 4: "adaptive_compacted"}; rows = []
    baseline_adaptive = load(args.baseline / "performance_alg4.json")
    for ci, condition in enumerate(conditions):
        cond = args.run / condition
        values = {alg: load(cond / f"performance_alg{alg}.json") for alg in methods}
        oracle = load(cond / "adaptive_oracle_analysis/bem_real_holdout_analysis.json")
        audit = load(cond / "openfast_audit/openfast_bem_summary.json")
        for alg, method in methods.items():
            item = values[alg]
            speed = independent(values[1]["end_to_end_times_ms"], item["end_to_end_times_ms"],
                                20260824 + ci * 10 + alg)
            rows.append({"condition": condition, "method": method,
                         "records": item["records"],
                         "kernel_median_ms": statistics.median(item["kernel_times_ms"]),
                         "e2e_median_ms": statistics.median(item["end_to_end_times_ms"]),
                         "brent_over_method_e2e": speed[0], "ci95_low": speed[1],
                         "ci95_high": speed[2], "solver_failures": item["solver_failures"],
                         "bootstrap_design": "independent_sequential_methods",
                         "oracle_n": oracle["n"], "oracle_failures_adaptive": oracle["failures"],
                         "openfast_shape_pass": audit["shape_and_channel_audit_pass"],
                         "openfast_finite_pass": audit["finite_audit_pass"]})
        variation = independent(values[4]["end_to_end_times_ms"],
                                baseline_adaptive["end_to_end_times_ms"], 20261000 + ci)
        rows[-1]["condition_over_12mps_adaptive_e2e"] = variation[0]
        rows[-1]["condition_over_12mps_ci_low"] = variation[1]
        rows[-1]["condition_over_12mps_ci_high"] = variation[2]
    fields = sorted({key for row in rows for key in row})
    with (args.out / "openfast_multicondition_bootstrap.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
