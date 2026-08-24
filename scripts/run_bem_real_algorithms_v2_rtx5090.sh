#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_algorithms_v2_rtx5090";mkdir -p "$out" build
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/validate_bem_real_algorithms_v2 src_cuda/validate_bem_real_algorithms_v2.cu && nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/benchmark_bem_real_v2 src_cuda/benchmark_bem_real.cu' >"$out/compile.log" 2>&1
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/validate_bem_real_algorithms_v2 --references references/bem_real_ref_v1_20260824/bem_real_reference.csv --out '$out'" | tee "$out/validation.log"
dataset=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin
for a in 0 1 2;do docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/benchmark_bem_real_v2 '$dataset' 30 '$a' '$out/roots_alg${a}.bin' 10" | tee "$out/performance_alg${a}.json";done
sha256sum src_cuda/validate_bem_real_algorithms_v2.cu src_cuda/benchmark_bem_real.cu include/bem_real_solver.h >"$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
