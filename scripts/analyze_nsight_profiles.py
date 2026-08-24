#!/usr/bin/env python3
"""Extract a compact, auditable metric table from Nsight Compute --set full CSV."""
import csv
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROFILES=ROOT/"profiles"
METRICS={
 "duration_ms":"gpu__time_duration.sum",
 "achieved_occupancy_pct":"sm__warps_active.avg.pct_of_peak_sustained_active",
 "active_warps_per_cycle":"sm__warps_active.avg.per_cycle_active",
 "eligible_warps_per_cycle":"smsp__warps_eligible.avg.per_cycle_active",
 "uniform_branch_pct":"smsp__sass_average_branch_targets_threads_uniform.pct",
 "threads_per_instruction":"smsp__thread_inst_executed_per_inst_executed.ratio",
 "dram_active_pct":"dram__cycles_active.avg.pct_of_peak_sustained_elapsed",
 "l1_hit_pct":"l1tex__t_sector_hit_rate.pct",
 "l2_hit_pct":"lts__t_sector_hit_rate.pct",
 "global_load_bytes_per_sector":"smsp__sass_average_data_bytes_per_sector_mem_global_op_ld.ratio",
 "global_store_bytes_per_sector":"smsp__sass_average_data_bytes_per_sector_mem_global_op_st.ratio",
 "registers_per_thread":"launch__registers_per_thread",
 "local_load_sectors":"l1tex__t_sectors_pipe_lsu_mem_local_op_ld.sum",
 "local_store_sectors":"l1tex__t_sectors_pipe_lsu_mem_local_op_st.sum",
 "shared_bank_conflicts":"l1tex__data_bank_conflicts_pipe_lsu_mem_shared.sum",
 "stall_barrier":"smsp__average_warps_issue_stalled_barrier_per_issue_active.ratio",
 "stall_branch_resolving":"smsp__average_warps_issue_stalled_branch_resolving_per_issue_active.ratio",
 "stall_long_scoreboard":"smsp__average_warps_issue_stalled_long_scoreboard_per_issue_active.ratio",
 "stall_math_pipe":"smsp__average_warps_issue_stalled_math_pipe_throttle_per_issue_active.ratio",
}

def read_one(path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        rows=csv.reader(f);header=next(rows);next(rows);values=next(rows)
    source=dict(zip(header,values))
    missing=[v for v in METRICS.values() if v not in source]
    if missing:raise RuntimeError(f"{path.name}: missing metrics {missing}")
    out={"profile":path.stem,"kernel":source["Kernel Name"]}
    for label,metric in METRICS.items():out[label]=float(source[metric] or "nan")
    out["warp_execution_efficiency_pct"]=100*out["threads_per_instruction"]/32
    return out

def fmt(x):return "—" if x!=x else f"{x:.4g}"
def main():
    paths=sorted(PROFILES.glob("adaptive_domain[0-4]_n131072.csv"))+sorted(PROFILES.glob("bem_real_algorithm[03].csv"))
    rows=[read_one(p) for p in paths]
    fields=list(rows[0])
    out=PROFILES/"nsight_summary.csv"
    with out.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    md=ROOT/"results_processed"/"NSIGHT_COMPUTE_RTX5090_V1.md"
    with md.open("w",encoding="utf-8",newline="\n") as f:
        f.write("# Nsight Compute profiling（RTX 5090）\n\n")
        f.write("所有条目使用 Nsight Compute `--set full`，每份报告只捕获一个目标 launch；profiler 的 replay 时间不得作为性能计时。\n\n")
        f.write("| profile | duration ms | occupancy % | active warps/cycle | eligible warps/cycle | uniform branch % | warp exec % | DRAM active % | L1 hit % | L2 hit % | registers/thread | local LD/ST sectors | branch stall | scoreboard stall | math stall |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in rows:
            f.write("| "+" | ".join([r["profile"],fmt(r["duration_ms"]),fmt(r["achieved_occupancy_pct"]),fmt(r["active_warps_per_cycle"]),fmt(r["eligible_warps_per_cycle"]),fmt(r["uniform_branch_pct"]),fmt(r["warp_execution_efficiency_pct"]),fmt(r["dram_active_pct"]),fmt(r["l1_hit_pct"]),fmt(r["l2_hit_pct"]),fmt(r["registers_per_thread"]),f'{fmt(r["local_load_sectors"])}/{fmt(r["local_store_sectors"])}',fmt(r["stall_branch_resolving"]),fmt(r["stall_long_scoreboard"]),fmt(r["stall_math_pipe"])])+" |\n")
        f.write("\n`bem_real_algorithm0` 是提前停止二分，`bem_real_algorithm3` 是固定 44 步低分歧二分。二进制 `.ncu-rep` 与完整宽表 CSV 保存在远端 `profiles/`，SHA-256 记录于 `profiles/sha256.txt`。\n")
    print(out);print(md)
if __name__=="__main__":main()
