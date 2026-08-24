#!/usr/bin/env bash
set -euo pipefail
cd /home/abc/supplementary_experiments
mkdir -p build
gcc -O3 -march=native -std=c17 -Wall -Wextra -Iinclude \
  src_c/validate_bem_real.c -lm -o build/validate_bem_real_alg
dataset=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin
for algorithm in 0 1 2; do
  ./build/validate_bem_real_alg "$dataset" 101 "$algorithm"
done
