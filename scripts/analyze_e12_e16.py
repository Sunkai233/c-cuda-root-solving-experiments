#!/usr/bin/env python3
import argparse,csv,json,math,random,statistics
from pathlib import Path

def loadj(path):
    return json.loads(path.read_text(encoding="utf-8").strip().splitlines()[-1])
def median(x): return statistics.median(x)
def ci_ratio(a,b,seed):
    r=random.Random(seed);z=[]
    for _ in range(10000):
        aa=[a[r.randrange(len(a))] for _ in a];bb=[b[r.randrange(len(b))] for _ in b]
        z.append(median(aa)/median(bb))
    z.sort();return median(a)/median(b),z[249],z[9749]
def write_csv(path,rows):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser();p.add_argument("run",type=Path);p.add_argument("--out",type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    cert={}
    for split in ("dev","cal","test"):
        rows=list(csv.DictReader((a.run/f"certificate_{split}"/"certificate_summary.csv").open(encoding="utf-8")))
        cert[split]=rows
    test={(r["path"],r["gate"]):r for r in cert["test"]}
    adaptive=list(csv.DictReader((a.run/"certificate_test"/"certificate_adaptive_samples.csv").open(encoding="utf-8")))
    adaptive_fail=sum(float(r["root_abs"])>1e-7 or int(r["status"])==0 for r in adaptive)
    adaptive_paths={str(k):sum(int(r["path"])==k for r in adaptive) for k in range(3)}

    perf=[loadj(a.run/"performance"/f"method_{i}.json") for i in range(5)]
    base=perf[0];prows=[]
    for i,x in enumerate(perf):
        ratio,lo,hi=ci_ratio(base["e2e_times_ms"],x["e2e_times_ms"],7100+i)
        prows.append({"method":x["method"],"kernel_median_ms":x["kernel_median_ms"],"e2e_median_ms":x["e2e_median_ms"],"fp64_over_method_e2e":ratio,"ci95_low":lo,"ci95_high":hi,"fp32":x["paths"]["fp32"],"df32":x["paths"]["df32"],"fp64":x["paths"]["fp64"],"solver_failures":x["solver_failures"]})
    write_csv(a.out/"certificate_performance_bootstrap.csv",prows)

    grows=[]
    for eps in ("1e-4","1e-5","1e-6","1e-7"):
        g=loadj(a.run/"goal"/f"method_0_eps_{eps}.json");u=loadj(a.run/"goal"/f"method_1_eps_{eps}.json")
        ratio,lo,hi=ci_ratio(u["times_ms"],g["times_ms"],8100+len(grows))
        grows.append({"epsilon":float(eps),"goal_median_ms":g["kernel_qoi_median_ms"],"uniform_median_ms":u["kernel_qoi_median_ms"],"uniform_over_goal":ratio,"ci95_low":lo,"ci95_high":hi,"goal_fp32":g["paths"]["fp32"],"goal_df32":g["paths"]["df32"],"goal_fp64":g["paths"]["fp64"],"uniform_fp32":u["paths"]["fp32"],"uniform_df32":u["paths"]["df32"],"uniform_fp64":u["paths"]["fp64"],"predicted_bound":g["predicted_relative_bound"],"load_error":g["actual_load_relative_error"],"torque_error":g["actual_torque_relative_error"],"uniform_predicted_bound":u["predicted_relative_bound"],"uniform_load_error":u["actual_load_relative_error"],"uniform_torque_error":u["actual_torque_relative_error"],"bound_pass":max(g["actual_load_relative_error"],g["actual_torque_relative_error"])<=g["predicted_relative_bound"]})
    write_csv(a.out/"goal_budget_summary.csv",grows)

    routing=[];regrets=[];matches=0
    for ps in ("0","0.001","0.01","0.05","0.1","0.25","0.5","0.75","1"):
        forced=[loadj(a.run/"routing"/f"mode_{m}_p_{ps}.json") for m in range(4)];auto=loadj(a.run/"routing"/f"mode_4_p_{ps}.json")
        best=min(forced,key=lambda x:x["kernel_median_ms"]);ratio,lo,hi=ci_ratio(auto["times_ms"],best["times_ms"],9100+len(routing));regret=ratio-1;regrets.append(regret);matches+=auto["mode"]==best["mode"]
        routing.append({"p":float(ps),"p_observed":auto["p_observed"],"q_warp_model":auto["q_warp_model"],"best_mode":best["mode"],"best_median_ms":best["kernel_median_ms"],"auto_mode":auto["mode"],"auto_median_ms":auto["kernel_median_ms"],"auto_over_best":ratio,"ci95_low":lo,"ci95_high":hi,"regret_percent":100*regret,"inline_ms":forced[0]["kernel_median_ms"],"warp_ms":forced[1]["kernel_median_ms"],"block_ms":forced[2]["kernel_median_ms"],"global_ms":forced[3]["kernel_median_ms"]})
    write_csv(a.out/"routing_summary.csv",routing)

    ablations=[
      {"module":"root posterior versus residual-only","evidence":"new frozen test FP32","full":int(test[("fp32","posterior")]["false_accept"]),"disabled":int(test[("fp32","residual")]["false_accept"]),"interpretation":"residual-only falsely accepts a wrong candidate"},
      {"module":"gradient certificate","evidence":"full-state performance","full":perf[4]["e2e_median_ms"],"disabled":perf[3]["e2e_median_ms"],"interpretation":"gradient certificate has measurable cost; root/branch correctness is unchanged"},
      {"module":"goal-oriented allocation","evidence":"four output budgets","full":max(r["load_error"] for r in grows),"disabled":max(r["load_error"] for r in grows),"interpretation":"compare path allocation and time against uniform tolerance; both retain branch witness"},
      {"module":"dynamic routing","evidence":"nine p values, independent ordering seed","full":100*max(regrets),"disabled":max(100*(r["inline_ms"]/r["best_median_ms"]-1) for r in routing),"interpretation":"values are worst regret percentages for auto and always-inline"},
      {"module":"df32 path","evidence":"full-state performance","full":perf[3]["e2e_median_ms"],"disabled":perf[0]["e2e_median_ms"],"interpretation":"certificate path versus all-FP64"},
      {"module":"robust fallback","evidence":"full-state performance","full":perf[3]["solver_failures"],"disabled":perf[1]["solver_failures"],"interpretation":"fixed df32 without fallback leaves failures"}
    ];write_csv(a.out/"e16_ablation_summary.csv",ablations)
    summary={"run":a.run.name,"frozen_test":{"n":len(adaptive),"adaptive_failures":adaptive_fail,"paths":adaptive_paths,"fp32_residual_false_accept":int(test[("fp32","residual")]["false_accept"]),"fp32_condition_false_accept":int(test[("fp32","condition")]["false_accept"]),"fp32_posterior_false_accept":int(test[("fp32","posterior")]["false_accept"]),"df32_posterior_false_accept":int(test[("df32","posterior")]["false_accept"])},"performance":prows,"goal":{"all_bounds_pass":all(r["bound_pass"] for r in grows),"rows":grows},"routing":{"auto_exact_mode_matches":matches,"points":len(routing),"max_regret_percent":100*max(regrets),"median_regret_percent":100*median(regrets)},"acceptance":{"false_accept_zero":int(test[("fp32","posterior")]["false_accept"])==0 and int(test[("df32","posterior")]["false_accept"])==0,"adaptive_failures_zero":adaptive_fail==0,"goal_bounds_pass":all(r["bound_pass"] for r in grows),"routing_failures_zero":all(loadj(x)["failures"]==0 for x in (a.run/"routing").glob("*.json"))}}
    (a.out/"analysis.json").write_text(json.dumps(summary,indent=2),encoding="utf-8");print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
