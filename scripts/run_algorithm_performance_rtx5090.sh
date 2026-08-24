#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_image="docker.m.daocloud.io/vllm/vllm-openai:latest"
runtime_image="nvidia/cuda:12.8.1-base-ubuntu24.04"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_algorithm_performance_rtx5090"
out="results_raw/$run_id";mkdir -p "$root/build/cuda_strict" "$root/$out"
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total,compute_cap --format=csv > "$root/$out/hardware_before.txt"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" \
  -lc 'set -o pipefail; nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/performance_algorithms src_cuda/performance_algorithms.cu -lgomp 2>&1 | tee build/cuda_strict/algorithm_performance_compile.log'
docker run --rm --gpus 'device=0' --entrypoint bash -v "$root:/work" -w /work \
  -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro "$runtime_image" \
  -lc "build/cuda_strict/performance_algorithms --out '$out' --max-n 16777216 --warmups 10 --repetitions 30 --heat-seconds 45" | tee "$root/$out/run.log"
nvidia-smi --query-gpu=name,temperature.gpu,power.draw,clocks.current.sm,clocks.current.memory --format=csv > "$root/$out/hardware_after.txt"
cp "$root/build/cuda_strict/algorithm_performance_compile.log" "$root/$out/compile.log"
sha256sum "$root/src_cuda/benchmark.cu" "$root/src_cuda/validate_algorithms.cu" "$root/src_cuda/performance_algorithms.cu" > "$root/$out/sha256.txt"
printf '%s\n' "$run_id" > "$root/results_raw/LATEST_ALGORITHM_PERFORMANCE"
echo "COMPLETE $run_id"
