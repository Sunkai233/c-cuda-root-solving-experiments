#!/usr/bin/env python3
"""Mechanical acceptance audit for the user-approved scope that excludes E8."""
import argparse
import csv
import json
from pathlib import Path


def csv_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--cpu-run", type=Path, required=True)
    parser.add_argument("--bem-cpu-run", type=Path, required=True)
    parser.add_argument("--cpu-fast-run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(); checks = []

    def check(name, condition, detail):
        checks.append({"name": name, "pass": bool(condition), "detail": str(detail)})

    scope = json.loads((root / "manifests/final_scope_no_e8_v1.json").read_text(encoding="utf-8"))
    wanted = ["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E9", "E10", "E11"]
    check("scope includes E0-E11 except E8", scope["included_experiments"] == wanted,
          scope["included_experiments"])
    check("scope excludes only E8", set(scope["excluded_experiments"]) == {"E8"},
          scope["excluded_experiments"])

    reports = [
        "FROZEN_CORRECTNESS_V3.md", "GPU_PERFORMANCE_V3_RTX5090.md",
        "ALGORITHM_PERFORMANCE_RTX5090_V1.md", "BEM_REAL_FROZEN_RTX5090_V1.md",
        "BEM_REAL_ALGORITHM_MATRIX_RTX5090_V2.md", "BEM_REAL_PRECISION_PATHS_RTX5090_V1.md",
        "BEM_REAL_FINITE_DIFFERENCE_V1.md", "BEM_SCALE_CONDITION_ABLATIONS_RTX5090.md",
        "PV_EXTENDED_GRADIENTS_RTX5090_V1.md", "CSTR_FOLD_VALIDATION_RTX5090_V1.md",
        "REMAINING_CUDA_ABLATIONS_RTX5090.md", "NSIGHT_COMPUTE_RTX5090_V1.md",
        "CPU_C17_PERFORMANCE_V1.md", "BEM_REAL_CPU_GPU_V1.md", "CPU_FAST_MATH_V1.md",
        "FINAL_ACCEPTANCE_NO_E8.md",
    ]
    for report in reports:
        check(f"report:{report}", (root / "results_processed" / report).is_file(), report)

    markers = [
        "TEST_SPLIT_EXECUTED_adaptive_v3_20260824.txt",
        "TEST_SPLIT_EXECUTED_bem_real_adaptive_v1_20260824.txt",
        "TEST_SPLIT_EXECUTED_bem_real_gradient_v1_20260824.txt",
        "TEST_SPLIT_EXECUTED_bem_real_precision_v2_20260824.txt",
        "TEST_SPLIT_EXECUTED_cstr_fold_v1_20260824.txt",
        "TEST_SPLIT_EXECUTED_pv_extended_v1_20260824.txt",
    ]
    for marker in markers:
        check(f"one-shot marker:{marker}", (root / "manifests" / marker).is_file(), marker)

    gpu_reps = root / "results_raw/20260824T092702Z_performance_gpu_v3_rtx5090/performance_repetitions.csv"
    alg_reps = root / "results_raw/20260824T015010Z_algorithm_performance_rtx5090/algorithm_performance_repetitions.csv"
    check("GPU matrix has 15,600 repetitions", csv_rows(gpu_reps) == 15600, csv_rows(gpu_reps))
    check("algorithm matrix has 16,380 repetitions", csv_rows(alg_reps) == 16380, csv_rows(alg_reps))

    for label, run in (("CPU C17", args.cpu_run), ("real BEM CPU", args.bem_cpu_run),
                       ("CPU fast candidate", args.cpu_fast_run)):
        check(f"{label} COMPLETE", (run / "COMPLETE.txt").is_file(), run)
    for filename in ("strict_serial.csv", "strict_simd.csv", "strict_omp96.csv", "pgo_omp96.csv"):
        path = args.cpu_run / filename
        check(f"CPU C17 {filename} has 1,950 repetitions", path.is_file() and csv_rows(path) == 1950,
              csv_rows(path) if path.is_file() else "missing")
    for filename in ("serial.csv", "omp96.csv"):
        path = args.bem_cpu_run / filename
        check(f"real BEM CPU {filename} has 120 repetitions", path.is_file() and csv_rows(path) == 120,
              csv_rows(path) if path.is_file() else "missing")
    check("CPU fast validation status recorded", (args.cpu_fast_run / "FAST_STATUS.txt").is_file(),
          args.cpu_fast_run / "FAST_STATUS.txt")
    check("CPU vector report recorded", (args.cpu_run / "vectorization.txt").is_file(),
          args.cpu_run / "vectorization.txt")
    check("CPU disassembly recorded", (args.cpu_run / "disassembly.txt").is_file(),
          args.cpu_run / "disassembly.txt")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = {"scope": "E0-E11 excluding E8", "passed": sum(x["pass"] for x in checks),
              "total": len(checks), "all_pass": all(x["pass"] for x in checks), "checks": checks}
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("scope", "passed", "total", "all_pass")}, ensure_ascii=False))
    if not result["all_pass"]: raise SystemExit(1)


if __name__ == "__main__":
    main()
