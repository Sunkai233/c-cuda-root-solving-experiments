#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";ref=references/ref_v3_20260824
run_id="$(date -u +%Y%m%dT%H%M%SZ)_specialized_validation_v3_rtx5090";out="results_raw/$run_id";mkdir -p build/cuda_strict "$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work docker.m.daocloud.io/vllm/vllm-openai:latest -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-DNDEBUG -o build/cuda_strict/validate_algorithms src_cuda/validate_algorithms.cu' >"$out/compile.log" 2>&1
docker run --rm --gpus 'device=0' --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/cuda_strict/validate_algorithms --references '$ref' --split cal --out '$out'" | tee "$out/run.log"
sha256sum "$ref"/*.csv src_cuda/benchmark.cu src_cuda/validate_algorithms.cu >"$out/sha256.txt";printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
