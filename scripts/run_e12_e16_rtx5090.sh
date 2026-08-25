#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
cd "$root"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_e12_e16_certificate_goal_routing_rtx5090"
out="results_raw/$run_id"
mkdir -p "$out" "$out/certificate_dev" "$out/certificate_cal" "$out/certificate_test" "$out/performance" "$out/goal" "$out/routing"
image_dev=nvidia/cuda:12.8.1-devel-ubuntu24.04
image_run=nvidia/cuda:12.8.1-base-ubuntu24.04
dataset=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin

nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,temperature.gpu,power.draw,clocks.sm --format=csv,noheader -i 0 > "$out/gpu_before.csv"
uname -a > "$out/uname.txt"
docker image inspect "$image_dev" --format '{{.Id}} {{index .RepoDigests 0}}' > "$out/container.txt" 2>&1 || docker image inspect "$image_dev" --format '{{.Id}}' > "$out/container.txt"

docker run --rm --gpus all -v "$root:/work" -w /work "$image_dev" bash -lc '
set -e
for n in validate_certificate_precision benchmark_certificate_precision benchmark_goal_budget benchmark_dynamic_routing; do
  nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -Xptxas=-v -lineinfo -o build/research_depth/$n src_cuda/$n.cu
done' > "$out/compile.log" 2>&1

run_cuda(){ docker run --rm --gpus 'device=0' -v "$root:/work" -w /work "$image_run" "$@"; }
run_cuda build/research_depth/validate_certificate_precision --references references/bem_real_ref_v1_20260824/bem_real_reference.csv --split dev --out "$out/certificate_dev" --tau-x 1e-7 --tau-g 2e-6 | tee "$out/certificate_dev.log"
run_cuda build/research_depth/validate_certificate_precision --references references/bem_real_ref_v1_20260824/bem_real_reference.csv --split cal --out "$out/certificate_cal" --tau-x 1e-7 --tau-g 2e-6 | tee "$out/certificate_cal.log"
run_cuda build/research_depth/validate_certificate_precision --references references/bem_real_ref_v5_certificate_test_20260825/bem_real_reference.csv --split test --out "$out/certificate_test" --tau-x 1e-7 --tau-g 2e-6 | tee "$out/certificate_test.log"
printf 'TEST_EXECUTED %s\n' "$run_id" > manifests/TEST_SPLIT_EXECUTED_certificate_v1_20260825.txt

for method in 0 1 2 3 4; do
  run_cuda build/research_depth/benchmark_certificate_precision "$dataset" "$method" 30 10 1e-7 2e-6 | tee "$out/performance/method_${method}.json"
done
for epsilon in 1e-4 1e-5 1e-6 1e-7; do
  for method in 0 1; do
    run_cuda build/research_depth/benchmark_goal_budget "$dataset" "$method" "$epsilon" 30 10 | tee "$out/goal/method_${method}_eps_${epsilon}.json"
  done
done
for p in 0 0.001 0.01 0.05 0.1 0.25 0.5 0.75 1; do
  for mode in 0 1 2 3 4; do
    run_cuda build/research_depth/benchmark_dynamic_routing "$dataset" "$mode" "$p" 30 10 27183 | tee "$out/routing/mode_${mode}_p_${p}.json"
  done
done

nvidia-smi --query-gpu=timestamp,name,uuid,driver_version,temperature.gpu,power.draw,clocks.sm --format=csv,noheader -i 0 > "$out/gpu_after.csv"
sha256sum manifests/frozen_certificate_goal_routing_v1.json references/bem_real_ref_v5_certificate_test_20260825/* include/bem_posterior_certificate.cuh src_cuda/validate_certificate_precision.cu src_cuda/benchmark_certificate_precision.cu src_cuda/benchmark_goal_budget.cu src_cuda/benchmark_dynamic_routing.cu scripts/run_e12_e16_rtx5090.sh > "$out/sha256.txt"
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
printf '%s\n' "$run_id"
