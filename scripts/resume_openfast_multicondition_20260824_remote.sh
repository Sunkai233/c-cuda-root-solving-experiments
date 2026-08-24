#!/usr/bin/env bash
set -euo pipefail

root=/home/abc/supplementary_experiments
wind_dir="$root/domains/bem/openfast/5MW_Baseline/Wind"
base_dir="$root/domains/bem/openfast/5MW_Baseline"
source_case="$root/domains/bem/openfast/5MW_Land_600s"
turbsim="$root/_deps/openfast_3a9d3f2/build_release/modules/turbsim/turbsim"
openfast="$root/_deps/openfast_3a9d3f2/build_release/glue-codes/openfast/openfast"
python_of=/home/abc/miniconda3/envs/of/bin/python
run_id=20260824T124112Z_openfast_multicondition_v1
out="$root/results_raw/$run_id"
cd "$root"

restore_governor() { bash "$root/scripts/set_cpu_governor_remote.sh" restore; }
trap restore_governor EXIT
docker run --rm --privileged -v /sys:/hostsys:rw nvidia/cuda:12.8.1-base-ubuntu24.04 \
  bash -lc 'for p in /hostsys/devices/system/cpu/cpufreq/policy*/scaling_governor; do printf "%s\n" performance >"$p"; done'

add_geomphi() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
needle = '"TnInd"\n'
if '"GeomPhi"\n' not in s:
    if needle not in s:
        raise RuntimeError("TnInd nodal output marker not found")
    p.write_text(s.replace(needle, needle + '"GeomPhi"\n', 1))
PY
}

finish_condition() {
  tag="$1"; seed="$2"
  cond="$out/$tag"; case_dir="$root/domains/bem/openfast/5MW_Land_600s_$tag"
  inp="$wind_dir/90m_${tag}.inp"; bts="$wind_dir/90m_${tag}.bts"
  inflow="$base_dir/NRELOffshrBsline5MW_InflowWind_${tag}.dat"
  aero="$case_dir/NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat"
  fst="$case_dir/5MW_600s_${tag}.fst"; outb="$case_dir/5MW_600s_${tag}.outb"
  add_geomphi "$aero"
  if [[ ! -f "$case_dir/OPENFAST_GEOMPHI_COMPLETE" ]]; then
    if [[ -f "$outb" ]]; then mv "$outb" "$case_dir/5MW_600s_${tag}_no_geomflag.outb"; fi
    if [[ -f "$cond/openfast.log" ]]; then mv "$cond/openfast.log" "$cond/openfast_no_geomflag.log"; fi
    (cd "$case_dir"; "$openfast" "$(basename "$fst")" >"$cond/openfast.log" 2>&1)
    grep -q 'OpenFAST terminated normally' "$cond/openfast.log"
    touch "$case_dir/OPENFAST_GEOMPHI_COMPLETE"
  fi
  if [[ ! -f "$cond/openfast_audit/openfast_bem_summary.json" ]] || \
     ! grep -q '"channels": 835' "$cond/openfast_audit/openfast_bem_summary.json"; then
    if [[ -d "$cond/openfast_audit.retry" ]]; then
      mv "$cond/openfast_audit.retry" "$cond/openfast_audit.retry.interrupted.$(date -u +%H%M%S)"
    fi
    "$python_of" "$root/scripts/analyze_openfast_bem.py" --outb "$outb" \
      --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" --out "$cond/openfast_audit.retry"
    if [[ -d "$cond/openfast_audit" ]]; then mv "$cond/openfast_audit" "$cond/openfast_audit.no_geomflag"; fi
    mv "$cond/openfast_audit.retry" "$cond/openfast_audit"
  fi
  if [[ ! -f "$cond/dataset/bem_real_f64_soa.bin" ]]; then
    if [[ -d "$cond/dataset" ]]; then mv "$cond/dataset" "$cond/dataset.failed.$(date -u +%H%M%S)"; fi
    "$python_of" "$root/scripts/export_bem_real_dataset.py" --outb "$outb" \
      --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" --out-dir "$cond/dataset"
  fi
  dataset="$cond/dataset/bem_real_f64_soa.bin"
  dataset_container="/work/results_raw/$run_id/$tag/dataset/bem_real_f64_soa.bin"
  cond_container="/work/results_raw/$run_id/$tag"
  if ! "$python_of" - "$cond" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
for alg in (0, 1, 4):
    j, r = p / f"performance_alg{alg}.json", p / f"roots_alg{alg}.bin"
    if not j.is_file() or not r.is_file() or json.loads(j.read_text()).get("repeats") != 30:
        raise SystemExit(1)
PY
  then
    nvidia-smi --query-gpu=timestamp,name,uuid,temperature.gpu,power.draw,clocks.sm \
      --format=csv,noheader -i 0 >"$cond/gpu_before.csv"
    set +e
    docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work \
      nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
      "timeout 45s bash -c 'while :; do build/benchmark_bem_real_v2 \"$dataset_container\" 1 1 /dev/null 0 >/dev/null; done'"
    heat_rc=$?; set -e; test "$heat_rc" -eq 124
    if [[ "$tag" == 8mps_* ]]; then order="1 4 0"; else order="4 0 1"; fi
    for alg in $order; do
      docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work \
        nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
        "build/benchmark_bem_real_v2 '$dataset_container' 30 '$alg' '$cond_container/roots_alg${alg}.bin' 10" \
        | tee "$cond/performance_alg${alg}.json"
    done
    nvidia-smi --query-gpu=timestamp,name,uuid,temperature.gpu,power.draw,clocks.sm \
      --format=csv,noheader -i 0 >"$cond/gpu_after.csv"
  fi
  if [[ ! -f "$cond/oracle_300/bem_real_reference.csv" ]]; then
    docker run --rm --entrypoint python3 -v "$root:/work" -w /work \
      docker.m.daocloud.io/vllm/vllm-openai:latest references/generate_bem_real_references.py \
      --dataset "$dataset_container" --baseline /work/domains/bem/openfast/5MW_Baseline \
      --bisection-roots "$cond_container/roots_alg0.bin" --brent-roots "$cond_container/roots_alg1.bin" \
      --out "$cond_container/oracle_300" --n 300 --seed "$seed"
  fi
  if [[ ! -f "$cond/adaptive_oracle_analysis/bem_real_holdout_analysis.json" ]]; then
    if "$python_of" "$root/scripts/analyze_bem_real_holdout.py" --references "$cond/oracle_300/bem_real_reference.csv" \
        --roots "$cond/roots_alg4.bin" --out "$cond/adaptive_oracle_analysis"; then
      printf 'ADAPTIVE_ORACLE_PASS\n' >"$cond/ADAPTIVE_STATUS.txt"
    else
      printf 'ADAPTIVE_ORACLE_FAIL\n' >"$cond/ADAPTIVE_STATUS.txt"
    fi
  fi
  sha256sum "$inp" "$bts" "$inflow" "$fst" "$outb" "$dataset" "$cond"/roots_alg*.bin \
    "$cond/oracle_300/bem_real_reference.csv" >"$cond/sha256.txt"
  printf 'condition_end=%s\n' "$(date -u +%FT%TZ)" >>"$cond/manifest.txt"
}

# The first condition already has valid TurbSim input and wind; only its
# OpenFAST output lacked GeomPhi.  Preserve it above and resume from OpenFAST.
finish_condition 8mps_C_seed27183 27183

# Build the untouched second condition, including GeomPhi before OpenFAST.
tag=16mps_A_seed39107; uref=16; seed=39107; turbclass=A
cond="$out/$tag"; case_dir="$root/domains/bem/openfast/5MW_Land_600s_$tag"
inp="$wind_dir/90m_${tag}.inp"; bts="$wind_dir/90m_${tag}.bts"
inflow="$base_dir/NRELOffshrBsline5MW_InflowWind_${tag}.dat"
mkdir -p "$cond" "$case_dir"
if [[ ! -s "$bts" ]]; then
  cp "$wind_dir/90m_12mps_twr.inp" "$inp"
  sed -i -E "s/^[[:space:]]*[0-9-]+([[:space:]]+RandSeed1)/      ${seed}\\1/; s/^\"[ABC]\"([[:space:]]+IECturbc)/\"${turbclass}\"\\1/; s/^[[:space:]]*[0-9.]+([[:space:]]+URef[[:space:]]+- Mean)/         ${uref}\\1/" "$inp"
  (cd "$wind_dir"; "$turbsim" "$(basename "$inp")" >"$cond/turbsim.log" 2>&1)
fi
if [[ ! -f "$case_dir/5MW_600s_${tag}.fst" ]]; then
  cp "$base_dir/NRELOffshrBsline5MW_InflowWind_12mps.dat" "$inflow"
  sed -i "s#Wind/90m_12mps_twr.bts#Wind/90m_${tag}.bts#" "$inflow"
  cp "$source_case"/*.dat "$case_dir/"
  cp "$source_case/5MW_600s_alpha.fst" "$case_dir/5MW_600s_${tag}.fst"
  sed -i "s#NRELOffshrBsline5MW_InflowWind_12mps.dat#NRELOffshrBsline5MW_InflowWind_${tag}.dat#" "$case_dir/5MW_600s_${tag}.fst"
fi
printf 'condition_start=%s\ntag=%s\nURef=%s\nseed=%s\nIEC_class=%s\n' "$(date -u +%FT%TZ)" "$tag" "$uref" "$seed" "$turbclass" >"$cond/manifest.txt"
finish_condition "$tag" "$seed"

sha256sum scripts/run_openfast_multicondition_remote.sh scripts/resume_openfast_multicondition_20260824_remote.sh \
  src_cuda/benchmark_bem_real.cu include/bem_real_solver.h >"$out/sha256.txt"
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
