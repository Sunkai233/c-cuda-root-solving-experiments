#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_pv_extended_devcal_rtx5090";mkdir -p "$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/validate_pv_extended src_cuda/validate_pv_extended.cu -lgomp'
for split in dev cal;do docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/validate_pv_extended --references references/pv_extended_ref_v1_20260824/pv_extended.csv --split '$split' --out '$out'";done
sha256sum references/pv_extended_ref_v1_20260824/* src_cuda/validate_pv_extended.cu > "$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
