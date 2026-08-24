#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root"
out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_fast_scan_sweep_devcal_rtx5090";mkdir -p "$out"
build_image=nvidia/cuda:12.8.1-devel-ubuntu24.04;runtime_image=nvidia/cuda:12.8.1-base-ubuntu24.04
dataset=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin
for scan in 4 8 16 32;do
  docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" -lc \
    "nvcc -std=c++17 -O3 -arch=sm_120 -DBEM_FAST_SCAN_CELLS=$scan --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/bem_scan_$scan src_cuda/benchmark_bem_real.cu"
  docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work "$runtime_image" -lc \
    "build/bem_scan_$scan '$dataset' 5 4 '$out/roots_$scan.bin' 3" | tee "$out/scan_$scan.json"
done
sha256sum include/bem_real_solver.h src_cuda/benchmark_bem_real.cu "$dataset" > "$out/sha256.txt"
printf 'COMPLETE %s\n' "$out" | tee "$out/COMPLETE.txt"
