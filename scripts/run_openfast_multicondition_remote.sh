#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
wind_dir="$root/domains/bem/openfast/5MW_Baseline/Wind"
base_dir="$root/domains/bem/openfast/5MW_Baseline"
source_case="$root/domains/bem/openfast/5MW_Land_600s"
turbsim="$root/_deps/openfast_3a9d3f2/build_release/modules/turbsim/turbsim"
openfast="$root/_deps/openfast_3a9d3f2/build_release/glue-codes/openfast/openfast"
python_of=/home/abc/miniconda3/envs/of/bin/python
run_id="$(date -u +%Y%m%dT%H%M%SZ)_openfast_multicondition_v1"
out="$root/results_raw/$run_id"; mkdir -p "$out"
cd "$root"
restore_governor() { bash "$root/scripts/set_cpu_governor_remote.sh" restore; }
trap restore_governor EXIT
docker run --rm --privileged -v /sys:/hostsys:rw nvidia/cuda:12.8.1-base-ubuntu24.04 \
  bash -lc 'for p in /hostsys/devices/system/cpu/cpufreq/policy*/scaling_governor; do printf "%s\n" performance >"$p"; done'
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work \
  nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/benchmark_bem_real_v2 src_cuda/benchmark_bem_real.cu' \
  >"$out/compile.log" 2>&1

run_condition() {
  tag="$1"; uref="$2"; seed="$3"; turbclass="$4"
  cond="$out/$tag"; case_dir="$root/domains/bem/openfast/5MW_Land_600s_$tag"
  inp="$wind_dir/90m_${tag}.inp"; bts="$wind_dir/90m_${tag}.bts"
  inflow="$base_dir/NRELOffshrBsline5MW_InflowWind_${tag}.dat"
  mkdir -p "$cond" "$case_dir"
  test ! -e "$bts"; test ! -e "$case_dir/5MW_600s_${tag}.outb"
  cp "$wind_dir/90m_12mps_twr.inp" "$inp"
  sed -i -E "s/^[[:space:]]*[0-9-]+([[:space:]]+RandSeed1)/      ${seed}\\1/; s/^\"[ABC]\"([[:space:]]+IECturbc)/\"${turbclass}\"\\1/; s/^[[:space:]]*[0-9.]+([[:space:]]+URef[[:space:]]+- Mean)/         ${uref}\\1/" "$inp"
  cp "$base_dir/NRELOffshrBsline5MW_InflowWind_12mps.dat" "$inflow"
  sed -i "s#Wind/90m_12mps_twr.bts#Wind/90m_${tag}.bts#" "$inflow"
  cp "$source_case"/*.dat "$case_dir/"
  cp "$source_case/5MW_600s_alpha.fst" "$case_dir/5MW_600s_${tag}.fst"
  sed -i "s#NRELOffshrBsline5MW_InflowWind_12mps.dat#NRELOffshrBsline5MW_InflowWind_${tag}.dat#" "$case_dir/5MW_600s_${tag}.fst"
  printf 'condition_start=%s\ntag=%s\nURef=%s\nseed=%s\nIEC_class=%s\n' "$(date -u +%FT%TZ)" "$tag" "$uref" "$seed" "$turbclass" >"$cond/manifest.txt"
  (cd "$wind_dir"; "$turbsim" "$(basename "$inp")" >"$cond/turbsim.log" 2>&1)
  (cd "$case_dir"; "$openfast" "5MW_600s_${tag}.fst" >"$cond/openfast.log" 2>&1)
  grep -q 'OpenFAST terminated normally' "$cond/openfast.log"
  "$python_of" "$root/scripts/analyze_openfast_bem.py" --outb "$case_dir/5MW_600s_${tag}.outb" \
    --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" --out "$cond/openfast_audit"
  "$python_of" "$root/scripts/export_bem_real_dataset.py" --outb "$case_dir/5MW_600s_${tag}.outb" \
    --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" --out-dir "$cond/dataset"
  dataset="$cond/dataset/bem_real_f64_soa.bin"
  nvidia-smi --query-gpu=timestamp,name,uuid,temperature.gpu,power.draw,clocks.sm \
    --format=csv,noheader -i 0 >"$cond/gpu_before.csv"
  set +e
  docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work \
    nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
    "timeout 45s bash -c 'while :; do build/benchmark_bem_real_v2 \"$dataset\" 1 1 /dev/null 0 >/dev/null; done'"
  heat_rc=$?; set -e; test "$heat_rc" -eq 124
  if [[ "$tag" == 8mps_* ]]; then order="1 4 0"; else order="4 0 1"; fi
  for alg in $order; do
    docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work \
      nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
      "build/benchmark_bem_real_v2 '$dataset' 30 '$alg' '$cond/roots_alg${alg}.bin' 10" \
      | tee "$cond/performance_alg${alg}.json"
  done
  nvidia-smi --query-gpu=timestamp,name,uuid,temperature.gpu,power.draw,clocks.sm \
    --format=csv,noheader -i 0 >"$cond/gpu_after.csv"
  "$python_of" "$root/references/generate_bem_real_references.py" --dataset "$dataset" \
    --baseline "$base_dir" --bisection-roots "$cond/roots_alg0.bin" --brent-roots "$cond/roots_alg1.bin" \
    --out "$cond/oracle_300" --n 300 --seed "$seed"
  "$python_of" "$root/scripts/analyze_bem_real_holdout.py" --references "$cond/oracle_300/bem_real_reference.csv" \
    --roots "$cond/roots_alg4.bin" --out "$cond/adaptive_oracle_analysis"
  sha256sum "$inp" "$bts" "$inflow" "$case_dir/5MW_600s_${tag}.fst" \
    "$case_dir/5MW_600s_${tag}.outb" "$dataset" "$cond"/roots_alg*.bin \
    "$cond/oracle_300/bem_real_reference.csv" >>"$cond/sha256.txt"
  printf 'condition_end=%s\n' "$(date -u +%FT%TZ)" >>"$cond/manifest.txt"
}

run_condition 8mps_C_seed27183 8 27183 C
run_condition 16mps_A_seed39107 16 39107 A
sha256sum scripts/run_openfast_multicondition_remote.sh src_cuda/benchmark_bem_real.cu \
  include/bem_real_solver.h >"$out/sha256.txt"
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
