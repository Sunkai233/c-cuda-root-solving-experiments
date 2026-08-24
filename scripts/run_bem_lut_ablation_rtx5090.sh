#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_lut_ablation_rtx5090";mkdir -p "$out"
image=nvidia/cuda:12.8.1-devel-ubuntu24.04;runtime=nvidia/cuda:12.8.1-base-ubuntu24.04
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$image" -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/bem_lut src_cuda/benchmark_bem_real.cu && nvcc -std=c++17 -O3 -arch=sm_120 -DBEM_DISABLE_O1_LUT --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/bem_binary src_cuda/benchmark_bem_real.cu'
dataset=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin
for method in lut binary;do docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work "$runtime" -lc \
 "build/bem_$method '$dataset' 30 4 '$out/${method}_roots.bin' 10" | tee "$out/$method.json";done
gcc -O3 -std=c17 src_c/compare_root_files.c -lm -o build/compare_root_files
build/compare_root_files "$out/lut_roots.bin" "$out/binary_roots.bin" | tee "$out/root_comparison.json"
sha256sum include/bem_real_solver.h include/bem_polar_lut.h src_cuda/benchmark_bem_real.cu "$dataset" > "$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
