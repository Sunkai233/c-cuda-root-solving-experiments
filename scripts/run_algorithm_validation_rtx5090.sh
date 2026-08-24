#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_image="docker.m.daocloud.io/vllm/vllm-openai:latest"
runtime_image="nvidia/cuda:12.8.1-base-ubuntu24.04"
ref="references/ref_v1_20260824"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_algorithm_validation_rtx5090"
out="results_raw/$run_id";mkdir -p "$root/build/cuda_strict" "$root/$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" \
  -lc 'set -o pipefail; nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-DNDEBUG -o build/cuda_strict/validate_algorithms src_cuda/validate_algorithms.cu 2>&1 | tee build/cuda_strict/algorithm_compile.log'
docker run --rm --gpus 'device=0' --entrypoint bash -v "$root:/work" -w /work "$runtime_image" \
  -lc "build/cuda_strict/validate_algorithms --references '$ref' --split cal --out '$out'" | tee "$root/$out/run.log"
cp "$root/build/cuda_strict/algorithm_compile.log" "$root/$out/compile.log"
sha256sum "$root/$ref"/*.csv "$root/src_cuda/benchmark.cu" "$root/src_cuda/validate_algorithms.cu" > "$root/$out/sha256.txt"
printf '%s\n' "$run_id" > "$root/results_raw/LATEST_ALGORITHM_VALIDATION"
echo "COMPLETE $run_id"
