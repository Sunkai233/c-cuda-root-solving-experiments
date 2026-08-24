#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_precision_performance_rtx5090";mkdir -p "$out" build
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -Xptxas=-v -o build/benchmark_bem_real_precision src_cuda/benchmark_bem_real_precision.cu' >"$out/compile.log" 2>&1
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/benchmark_bem_real_precision --dataset results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin --out '$out' --max-n 2448000" | tee "$out/run.log"
sha256sum src_cuda/benchmark_bem_real_precision.cu src_cuda/validate_bem_real_precision.cu include/bem_real_precision.cuh >"$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
