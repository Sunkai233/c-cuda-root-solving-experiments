#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_image="docker.m.daocloud.io/vllm/vllm-openai:latest"
runtime_image="nvidia/cuda:12.8.1-base-ubuntu24.04"
ref="references/ref_v1_20260824"
config="manifests/frozen_adaptive_v1.json"
marker="$root/results_raw/TEST_SPLIT_EXECUTED_adaptive_v1_20260824"
if [ -e "$marker" ]; then echo "REFUSE: frozen test was already executed" >&2; exit 20; fi
run_id="$(date -u +%Y%m%dT%H%M%SZ)_frozen_test_rtx5090"
out="results_raw/$run_id";mkdir -p "$root/build/cuda_strict" "$root/$out"
cp "$root/$config" "$root/$out/frozen_config.json"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" \
  -lc 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/validate src_cuda/validate_references.cu -lgomp 2>&1 | tee build/cuda_strict/validate_compile.log'
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work \
  -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro "$runtime_image" \
  -lc "build/cuda_strict/validate --references '$ref' --out '$out' --split test --frozen-only" | tee "$root/$out/test.log"
cp "$root/build/cuda_strict/validate_compile.log" "$root/$out/compile.log"
sha256sum "$root/$ref"/*.csv "$root/$config" "$root/src_cuda/benchmark.cu" "$root/src_cuda/validate_references.cu" > "$root/$out/sha256.txt"
printf '%s\n' "$run_id" > "$marker";printf '%s\n' "$run_id" > "$root/results_raw/LATEST_FROZEN_TEST"
echo "COMPLETE $run_id"
