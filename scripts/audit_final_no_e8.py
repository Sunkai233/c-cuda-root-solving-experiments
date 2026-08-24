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
    parser.add_argument("--multicond-run", type=Path, required=True)
    parser.add_argument("--algorithm-v2-run", type=Path, required=True)
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
        "ALGORITHM_PERFORMANCE_RTX5090_V2.md", "BEM_REAL_FROZEN_RTX5090_V1.md",
        "BEM_REAL_ALGORITHM_MATRIX_RTX5090_V2.md", "BEM_REAL_PRECISION_PATHS_RTX5090_V1.md",
        "BEM_REAL_FINITE_DIFFERENCE_V1.md", "BEM_SCALE_CONDITION_ABLATIONS_RTX5090.md",
        "PV_EXTENDED_GRADIENTS_RTX5090_V1.md", "CSTR_FOLD_VALIDATION_RTX5090_V1.md",
        "REMAINING_CUDA_ABLATIONS_RTX5090.md", "NSIGHT_COMPUTE_RTX5090_V1.md",
        "CPU_C17_PERFORMANCE_V1.md", "BEM_REAL_CPU_GPU_V1.md", "CPU_FAST_MATH_V1.md",
        "BEM_OPENFAST_MULTICONDITION_V1.md",
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
    check("algorithm v2 COMPLETE", (args.algorithm_v2_run / "COMPLETE.txt").is_file(),
          args.algorithm_v2_run)
    v2_summary = args.algorithm_v2_run / "algorithm_performance.csv"
    v2_reps = args.algorithm_v2_run / "algorithm_performance_repetitions.csv"
    check("algorithm v2 has 325 summary groups", v2_summary.is_file() and csv_rows(v2_summary) == 325,
          csv_rows(v2_summary) if v2_summary.is_file() else "missing")
    check("algorithm v2 has 19,500 raw repetitions", v2_reps.is_file() and csv_rows(v2_reps) == 19500,
          csv_rows(v2_reps) if v2_reps.is_file() else "missing")
    if v2_summary.is_file():
        methods = {row["method"] for row in csv.DictReader(v2_summary.open(encoding="utf-8"))}
    else: methods = set()
    required_methods = {"mikkola_kepler", "lambert_w", "chandrupatla", "bishop_transform"}
    check("algorithm v2 includes all specialized methods", required_methods <= methods, sorted(methods))
    for split in ("dev", "cal"):
        validation = args.algorithm_v2_run / f"algorithm_validation_{split}.csv"
        check(f"algorithm v2 {split} validation recorded", validation.is_file(), validation)

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
    bem_validation = args.bem_cpu_run / "validation/bem_cpu_validation_summary.csv"
    check("real BEM CPU oracle validation has four methods",
          bem_validation.is_file() and csv_rows(bem_validation) == 4,
          csv_rows(bem_validation) if bem_validation.is_file() else "missing")
    check("real BEM CPU validation status recorded",
          (args.bem_cpu_run / "VALIDATION_STATUS.txt").is_file(),
          args.bem_cpu_run / "VALIDATION_STATUS.txt")
    check("CPU fast validation status recorded", (args.cpu_fast_run / "FAST_STATUS.txt").is_file(),
          args.cpu_fast_run / "FAST_STATUS.txt")
    for filename in ("fast_omp96.csv", "strict_nolto_omp96.csv"):
        path = args.cpu_fast_run / filename
        check(f"CPU compilation candidate {filename} has 1,950 repetitions",
              path.is_file() and csv_rows(path) == 1950,
              csv_rows(path) if path.is_file() else "missing")
    check("CPU no-LTO frozen-reference validation recorded",
          (args.cpu_fast_run / "nolto_validation/validation_test.csv").is_file(),
          args.cpu_fast_run / "nolto_validation/validation_test.csv")
    check("CPU no-LTO status recorded", (args.cpu_fast_run / "NO_LTO_STATUS.txt").is_file(),
          args.cpu_fast_run / "NO_LTO_STATUS.txt")
    check("CPU vector report recorded", (args.cpu_run / "vectorization.txt").is_file(),
          args.cpu_run / "vectorization.txt")
    check("CPU disassembly recorded", (args.cpu_run / "disassembly.txt").is_file(),
          args.cpu_run / "disassembly.txt")
    check("OpenFAST multi-condition COMPLETE", (args.multicond_run / "COMPLETE.txt").is_file(),
          args.multicond_run)
    for condition in ("8mps_C_seed27183", "16mps_A_seed39107"):
        cond = args.multicond_run / condition
        audit = cond / "openfast_audit/openfast_bem_summary.json"
        oracle = cond / "adaptive_oracle_analysis/bem_real_holdout_analysis.json"
        audit_data = json.loads(audit.read_text()) if audit.is_file() else {}
        oracle_data = json.loads(oracle.read_text()) if oracle.is_file() else {}
        check(f"{condition} OpenFAST shape and finite audit",
              audit_data.get("shape_and_channel_audit_pass") is True and
              audit_data.get("finite_audit_pass") is True, audit_data)
        check(f"{condition} adaptive oracle has zero failures",
              oracle_data.get("n") == 300 and oracle_data.get("failures") == 0, oracle_data)
        for algorithm in (0, 1, 4):
            performance = cond / f"performance_alg{algorithm}.json"
            perf = json.loads(performance.read_text()) if performance.is_file() else {}
            check(f"{condition} algorithm {algorithm} has 30 repetitions",
                  perf.get("repeats") == 30 and perf.get("solver_failures") == 0, perf)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = {"scope": "E0-E11 excluding E8", "passed": sum(x["pass"] for x in checks),
              "total": len(checks), "all_pass": all(x["pass"] for x in checks), "checks": checks}
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("scope", "passed", "total", "all_pass")}, ensure_ascii=False))
    if not result["all_pass"]: raise SystemExit(1)


if __name__ == "__main__":
    main()
