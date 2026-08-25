#!/usr/bin/env bash
set -euo pipefail

root="${E8_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
gpu="${GPU_INDEX:-0}"
dataset="${E8_DATASET:-$root/results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin}"
nvcc_bin="${NVCC:-/usr/local/cuda/bin/nvcc}"
cd "$root"

cc="$(nvidia-smi -i "$gpu" --query-gpu=compute_cap --format=csv,noheader | tr -d ' .\r')"
name="$(nvidia-smi -i "$gpu" --query-gpu=name --format=csv,noheader | tr ' /' '__' | tr -cd '[:alnum:]_.-')"
arch="sm_${cc}"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_e8_cross_arch_${name}_${arch}"
out="results_raw/$run_id"
build="build/e8/$arch"
mkdir -p "$out"/{certificate_dev,certificate_cal,certificate_test,performance,goal,routing_cal,routing_test} "$build"
test -f "$dataset"

nvidia-smi -i "$gpu" --query-gpu=timestamp,index,name,uuid,compute_cap,driver_version,pci.bus_id,pcie.link.gen.current,pcie.link.width.current,memory.total,power.limit,power.draw,temperature.gpu,clocks.sm,clocks.mem,ecc.mode.current --format=csv,noheader > "$out/gpu_before.csv"
nvidia-smi -i "$gpu" -q > "$out/nvidia_smi_q_before.txt"
uname -a > "$out/uname.txt"
"$nvcc_bin" --version > "$out/nvcc.txt"
printf 'gpu_index=%s\nname=%s\ncompute_capability=%s\narch=%s\n' "$gpu" "$name" "${cc:0:${#cc}-1}.${cc: -1}" "$arch" > "$out/identity.txt"

for n in validate_certificate_precision benchmark_certificate_precision benchmark_goal_budget benchmark_dynamic_routing; do
  "$nvcc_bin" -std=c++17 -O3 -arch="$arch" --fmad=true --ftz=false --prec-div=true --prec-sqrt=true \
    -Iinclude -Xptxas=-v -lineinfo -o "$build/$n" "src_cuda/$n.cu"
done > "$out/compile.log" 2>&1

"$build/validate_certificate_precision" --references references/bem_real_ref_v1_20260824/bem_real_reference.csv --split dev --out "$out/certificate_dev" --tau-x 1e-7 --tau-g 2e-6 | tee "$out/certificate_dev.log"
"$build/validate_certificate_precision" --references references/bem_real_ref_v1_20260824/bem_real_reference.csv --split cal --out "$out/certificate_cal" --tau-x 1e-7 --tau-g 2e-6 | tee "$out/certificate_cal.log"
"$build/validate_certificate_precision" --references references/bem_real_ref_v5_certificate_test_20260825/bem_real_reference.csv --split test --out "$out/certificate_test" --tau-x 1e-7 --tau-g 2e-6 | tee "$out/certificate_test.log"
printf 'E8_REPLICATION_TEST_EXECUTED %s\n' "$run_id" > "$out/TEST_EXECUTED.txt"

for method in 0 1 2 3 4; do
  "$build/benchmark_certificate_precision" "$dataset" "$method" 30 10 1e-7 2e-6 | tee "$out/performance/method_${method}.json"
done
for epsilon in 1e-4 1e-5 1e-6 1e-7; do
  for method in 0 1; do
    "$build/benchmark_goal_budget" "$dataset" "$method" "$epsilon" 30 10 | tee "$out/goal/method_${method}_eps_${epsilon}.json"
  done
done
for p in 0 0.001 0.01 0.05 0.1 0.25 0.5 0.75 1; do
  for mode in 0 1 2 3; do
    "$build/benchmark_dynamic_routing" "$dataset" "$mode" "$p" 30 10 17041 | tee "$out/routing_cal/mode_${mode}_p_${p}.json"
  done
  for mode in 0 1 2 3 4; do
    "$build/benchmark_dynamic_routing" "$dataset" "$mode" "$p" 30 10 27183 | tee "$out/routing_test/mode_${mode}_p_${p}.json"
  done
done

nvidia-smi -i "$gpu" --query-gpu=timestamp,index,name,uuid,compute_cap,driver_version,pci.bus_id,pcie.link.gen.current,pcie.link.width.current,memory.total,power.limit,power.draw,temperature.gpu,clocks.sm,clocks.mem,ecc.mode.current --format=csv,noheader > "$out/gpu_after.csv"
nvidia-smi -i "$gpu" -q > "$out/nvidia_smi_q_after.txt"
sha256sum manifests/frozen_e8_cross_architecture_v1.json references/bem_real_ref_v5_certificate_test_20260825/* \
  include/bem_posterior_certificate.cuh src_cuda/validate_certificate_precision.cu \
  src_cuda/benchmark_certificate_precision.cu src_cuda/benchmark_goal_budget.cu \
  src_cuda/benchmark_dynamic_routing.cu scripts/run_e8_cross_architecture.sh "$dataset" > "$out/sha256.txt"
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
printf '%s\n' "$run_id"
