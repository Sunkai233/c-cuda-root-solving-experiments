#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_precision_devcal_rtx5090";mkdir -p "$out" build
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -Xptxas=-v -o build/validate_bem_real_precision src_cuda/validate_bem_real_precision.cu' >"$out/compile.log" 2>&1
for split in dev cal;do docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/validate_bem_real_precision --references references/bem_real_ref_v1_20260824/bem_real_reference.csv --split '$split' --out '$out'" | tee -a "$out/run.log";done
sha256sum include/bem_real_precision.cuh include/df32.cuh src_cuda/validate_bem_real_precision.cu references/bem_real_ref_v1_20260824/* >"$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
