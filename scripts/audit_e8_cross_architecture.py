#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, default=Path(".")); ap.add_argument("--run", type=Path, required=True); ap.add_argument("--processed", type=Path, required=True); ap.add_argument("--out", type=Path, required=True); ap.add_argument("--expected-model", required=True); ap.add_argument("--expected-cc", required=True); ap.add_argument("--expected-arch", required=True); a = ap.parse_args()
    root = a.root; run = root / a.run; processed = root / a.processed; checks = []
    def check(name, ok, detail): checks.append({"name": name, "pass": bool(ok), "detail": str(detail)})
    manifest = json.loads((root / "manifests/frozen_e8_cross_architecture_v1.json").read_text(encoding="utf-8"))
    summary = json.loads((processed / "summary.json").read_text(encoding="utf-8"))
    check("formal COMPLETE", (run / "COMPLETE.txt").is_file(), run / "COMPLETE.txt")
    check("replication test marker", (run / "TEST_EXECUTED.txt").is_file(), run / "TEST_EXECUTED.txt")
    for label, spec in (("dataset", manifest["dataset"]), ("frozen test", manifest["frozen_test"])):
        actual = hashlib.sha256((root / spec["path"]).read_bytes()).hexdigest(); check(f"{label} SHA-256", actual == spec["sha256"], actual)
    device = summary["device"]
    identity_ok = (a.expected_model == device["name"] and device["compute_capability"] == a.expected_cc and device["arch"] == a.expected_arch)
    check("declared native device identity", identity_ok, device)
    check("five performance methods", len(list((run / "performance").glob("method_*.json"))) == 5, 5)
    check("eight goal configurations", len(list((run / "goal").glob("*.json"))) == 8, 8)
    check("36 routing calibration configurations", len(list((run / "routing_cal").glob("*.json"))) == 36, 36)
    check("45 routing test configurations", len(list((run / "routing_test").glob("*.json"))) == 45, 45)
    for folder in ("performance", "goal", "routing_cal", "routing_test"):
        values = [json.loads(p.read_text(encoding="utf-8")) for p in (run / folder).glob("*.json")]
        check(f"{folder} 30 repetitions", all((x.get("repetitions") == 30 or len(x.get("times_ms", [])) == 30) for x in values), len(values))
    check("correctness transfer", summary["acceptance"]["correctness_transfer"], summary["correctness"])
    check("goal budget transfer", summary["acceptance"]["goal_budget_transfer"], summary["goal_all_bounds_pass"])
    check("all routing failures zero", summary["routing"]["all_failures_zero"], summary["routing"])
    observed_transfer = summary["acceptance"]["rtx5090_threshold_transfer_5pct"]
    classified_transfer = (summary["routing"]["frozen_max_regret_percent"] <= manifest["acceptance"]["frozen_rtx5090_policy_max_regret_percent_for_threshold_transfer_claim"])
    check("RTX5090 threshold transfer classification consistent", observed_transfer == classified_transfer, {"transfer": observed_transfer, "max_regret_percent": summary["routing"]["frozen_max_regret_percent"]})
    result = {"scope": f"E8 {a.expected_model} cross-architecture replication", "passed": sum(x["pass"] for x in checks), "total": len(checks), "all_pass": all(x["pass"] for x in checks), "checks": checks}
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(result, indent=2), encoding="utf-8"); print(json.dumps({k: result[k] for k in ("scope", "passed", "total", "all_pass")})); return 0 if result["all_pass"] else 3

if __name__ == "__main__": raise SystemExit(main())
