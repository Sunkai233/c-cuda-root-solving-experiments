#!/usr/bin/env python3
import argparse, csv, json, random, statistics
from pathlib import Path

PVALS = ("0", "0.001", "0.01", "0.05", "0.1", "0.25", "0.5", "0.75", "1")

def loadj(path):
    return json.loads(path.read_text(encoding="utf-8").strip().splitlines()[-1])

def boot_ratio(a, b, seed, n=10000):
    rng = random.Random(seed); values = []
    for _ in range(n):
        aa = [a[rng.randrange(len(a))] for _ in a]
        bb = [b[rng.randrange(len(b))] for _ in b]
        values.append(statistics.median(aa) / statistics.median(bb))
    values.sort()
    return statistics.median(a) / statistics.median(b), values[249], values[9749]

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("run", type=Path); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    identity = dict(line.split("=", 1) for line in (a.run / "identity.txt").read_text().splitlines() if "=" in line)
    perf = [loadj(a.run / "performance" / f"method_{i}.json") for i in range(5)]
    perf_rows = []
    for i, x in enumerate(perf):
        e2e, elo, ehi = boot_ratio(perf[0]["e2e_times_ms"], x["e2e_times_ms"], 8260 + i)
        ker, klo, khi = boot_ratio(perf[0]["kernel_times_ms"], x["kernel_times_ms"], 8360 + i)
        perf_rows.append({"method": x["method"], "kernel_median_ms": x["kernel_median_ms"], "e2e_median_ms": x["e2e_median_ms"], "fp64_over_method_kernel": ker, "kernel_ci95_low": klo, "kernel_ci95_high": khi, "fp64_over_method_e2e": e2e, "e2e_ci95_low": elo, "e2e_ci95_high": ehi, "fp32": x["paths"]["fp32"], "df32": x["paths"]["df32"], "fp64": x["paths"]["fp64"], "solver_failures": x["solver_failures"]})
    write_csv(a.out / "performance.csv", perf_rows)

    goal_rows = []
    for eps in ("1e-4", "1e-5", "1e-6", "1e-7"):
        g = loadj(a.run / "goal" / f"method_0_eps_{eps}.json"); u = loadj(a.run / "goal" / f"method_1_eps_{eps}.json")
        ratio, lo, hi = boot_ratio(u["times_ms"], g["times_ms"], 8460 + len(goal_rows))
        goal_rows.append({"epsilon": float(eps), "goal_median_ms": g["kernel_qoi_median_ms"], "uniform_median_ms": u["kernel_qoi_median_ms"], "uniform_over_goal": ratio, "ci95_low": lo, "ci95_high": hi, "predicted_bound": g["predicted_relative_bound"], "load_error": g["actual_load_relative_error"], "torque_error": g["actual_torque_relative_error"], "bound_pass": max(g["actual_load_relative_error"], g["actual_torque_relative_error"]) <= g["predicted_relative_bound"], "goal_failures": g["solver_failures"], "uniform_failures": u["solver_failures"]})
    write_csv(a.out / "goal.csv", goal_rows)

    routing_rows = []
    for ps in PVALS:
        cal = [loadj(a.run / "routing_cal" / f"mode_{m}_p_{ps}.json") for m in range(4)]
        test = [loadj(a.run / "routing_test" / f"mode_{m}_p_{ps}.json") for m in range(5)]
        best_cal = min(cal, key=lambda x: x["kernel_median_ms"]); best_test = min(test[:4], key=lambda x: x["kernel_median_ms"])
        cal_choice_test = next(x for x in test[:4] if x["mode"] == best_cal["mode"]); frozen = test[4]
        fr, flo, fhi = boot_ratio(frozen["times_ms"], best_test["times_ms"], 8560 + len(routing_rows))
        cr, clo, chi = boot_ratio(cal_choice_test["times_ms"], best_test["times_ms"], 8660 + len(routing_rows))
        routing_rows.append({"p": float(ps), "test_best_mode": best_test["mode"], "test_best_ms": best_test["kernel_median_ms"], "rtx5090_frozen_mode": frozen["mode"], "rtx5090_frozen_ms": frozen["kernel_median_ms"], "frozen_regret_percent": 100 * (fr - 1), "frozen_ci95_low_percent": 100 * (flo - 1), "frozen_ci95_high_percent": 100 * (fhi - 1), "cal_best_mode": best_cal["mode"], "cal_choice_test_ms": cal_choice_test["kernel_median_ms"], "calibrated_regret_percent": 100 * (cr - 1), "calibrated_ci95_low_percent": 100 * (clo - 1), "calibrated_ci95_high_percent": 100 * (chi - 1), "failures": sum(x["failures"] for x in cal + test)})
    write_csv(a.out / "routing.csv", routing_rows)

    test_summary = list(csv.DictReader((a.run / "certificate_test" / "certificate_summary.csv").open(encoding="utf-8")))
    gate = {(r["path"], r["gate"]): int(r["false_accept"]) for r in test_summary}
    adaptive = list(csv.DictReader((a.run / "certificate_test" / "certificate_adaptive_samples.csv").open(encoding="utf-8")))
    adaptive_failures = sum(float(r["root_abs"]) > 1e-7 or int(r["status"]) == 0 for r in adaptive)
    summary = {"run": a.run.name, "device": identity, "correctness": {"fp32_posterior_false_accept": gate[("fp32", "posterior")], "df32_posterior_false_accept": gate[("df32", "posterior")], "fp32_residual_false_accept": gate[("fp32", "residual")], "adaptive_failures": adaptive_failures}, "performance": perf_rows, "goal_all_bounds_pass": all(x["bound_pass"] for x in goal_rows), "routing": {"frozen_max_regret_percent": max(x["frozen_regret_percent"] for x in routing_rows), "calibrated_max_regret_percent": max(x["calibrated_regret_percent"] for x in routing_rows), "all_failures_zero": all(x["failures"] == 0 for x in routing_rows)}, "acceptance": {"correctness_transfer": gate[("fp32", "posterior")] == 0 and gate[("df32", "posterior")] == 0 and adaptive_failures == 0, "goal_budget_transfer": all(x["bound_pass"] for x in goal_rows), "rtx5090_threshold_transfer_5pct": max(x["frozen_regret_percent"] for x in routing_rows) <= 5.0}}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__": main()
