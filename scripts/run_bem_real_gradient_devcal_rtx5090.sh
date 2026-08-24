#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_gradient_devcal_rtx5090";mkdir -p "$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/validate_bem_real_gradients src_cuda/validate_bem_real_gradients.cu'
for split in dev cal;do docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/validate_bem_real_gradients --references references/bem_real_ref_v1_20260824/bem_real_reference.csv --split '$split' --out '$out'";done
sha256sum references/bem_real_ref_v1_20260824/* include/bem_real_solver.h src_cuda/validate_bem_real_gradients.cu > "$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
