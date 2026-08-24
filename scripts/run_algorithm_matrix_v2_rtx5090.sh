#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments; cd "$root"
build_image=docker.m.daocloud.io/vllm/vllm-openai:latest
runtime_image=nvidia/cuda:12.8.1-base-ubuntu24.04
run_id="$(date -u +%Y%m%dT%H%M%SZ)_algorithm_matrix_v2_rtx5090"
out="results_raw/$run_id"; mkdir -p "$out" build/cuda_strict
restore_governor() { bash "$root/scripts/set_cpu_governor_remote.sh" restore; }
trap restore_governor EXIT
docker run --rm --privileged -v /sys:/hostsys:rw nvidia/cuda:12.8.1-base-ubuntu24.04 \
  bash -lc 'for p in /hostsys/devices/system/cpu/cpufreq/policy*/scaling_governor; do printf "%s\n" performance >"$p"; done'
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total,compute_cap \
  --format=csv >"$out/hardware_before.csv"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" -lc '
  set -o pipefail
  nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true \
    -Xptxas=-v -Xcompiler=-O3,-march=native,-DNDEBUG \
    -o build/cuda_strict/validate_algorithms src_cuda/validate_algorithms.cu
  nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true \
    -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG \
    -o build/cuda_strict/performance_algorithms src_cuda/performance_algorithms.cu -lgomp
' >"$out/compile.log" 2>&1
for split in dev cal; do
  docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work "$runtime_image" -lc \
    "build/cuda_strict/validate_algorithms --references references/ref_v3_20260824 --split '$split' --out '$out'" \
    | tee -a "$out/validation.log"
done
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work \
  -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro \
  "$runtime_image" -lc \
  "build/cuda_strict/performance_algorithms --out '$out' --max-n 16777216 --warmups 10 --repetitions 30 --heat-seconds 45" \
  | tee "$out/performance.log"
python scripts/analyze_algorithms.py "$out" --bootstrap 10000 | tee "$out/analysis.log"
nvidia-smi --query-gpu=name,temperature.gpu,power.draw,clocks.current.sm,clocks.current.memory \
  --format=csv >"$out/hardware_after.csv"
sha256sum references/ref_v3_20260824/*.csv src_cuda/benchmark.cu \
  src_cuda/validate_algorithms.cu src_cuda/performance_algorithms.cu scripts/analyze_algorithms.py \
  >"$out/sha256.txt"
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
