#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_image="docker.m.daocloud.io/vllm/vllm-openai:latest"
runtime_image="nvidia/cuda:12.8.1-base-ubuntu24.04"
out="results_raw/algorithm_performance_smoke"
mkdir -p "$root/build/cuda_strict" "$root/$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" \
  -lc 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/performance_algorithms src_cuda/performance_algorithms.cu -lgomp'
docker run --rm --gpus 'device=0' --entrypoint bash -v "$root:/work" -w /work \
  -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro "$runtime_image" \
  -lc "build/cuda_strict/performance_algorithms --out '$out' --max-n 131072 --warmups 2 --repetitions 2 --heat-seconds 1"
awk -F, 'NR>1 && $10 != 0 {bad += $10} END {print "wrong_root_total=" bad+0; exit(bad != 0)}' "$root/$out/algorithm_performance.csv"
