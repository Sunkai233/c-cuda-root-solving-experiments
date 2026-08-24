#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
dataset="$root/results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin"
out="$root/results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_algorithm_matrix_rtx5090"
build_image=docker.m.daocloud.io/vllm/vllm-openai:latest
runtime_image=nvidia/cuda:12.8.1-base-ubuntu24.04
mkdir -p "$root/build" "$out"
cd "$root"
gcc -O3 -march=native -std=c17 -Wall -Wextra -Iinclude \
  src_c/validate_bem_real.c -lm -o build/validate_bem_real_alg
gcc -O3 -std=c17 -Wall -Wextra src_c/compare_root_files.c -lm -o build/compare_root_files
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -Xptxas=-v -o build/benchmark_bem_real_alg src_cuda/benchmark_bem_real.cu' \
  > "$out/compile.log" 2>&1
for algorithm in 0 1 2; do
  build/validate_bem_real_alg "$dataset" 1 "$algorithm" "$out/cpu_roots_alg${algorithm}.bin" \
    | tee "$out/cpu_alg${algorithm}.json"
  docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$runtime_image" -lc \
    "build/benchmark_bem_real_alg results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin 30 $algorithm ${out#"$root/"}/gpu_roots_alg${algorithm}.bin" \
    | tee "$out/gpu_alg${algorithm}_30.json"
  build/compare_root_files "$out/cpu_roots_alg${algorithm}.bin" "$out/gpu_roots_alg${algorithm}.bin" \
    | tee "$out/cpu_gpu_alg${algorithm}.json"
done
sha256sum src_c/validate_bem_real.c src_c/compare_root_files.c src_cuda/benchmark_bem_real.cu \
  include/bem_real_solver.h include/bem_real_tables.h "$dataset" > "$out/sha256.txt"
nvidia-smi --query-gpu=name,uuid,driver_version,compute_cap --format=csv > "$out/hardware.txt"
lscpu > "$out/cpu_hardware.txt"
printf '%s\n' "$out"
