#!/usr/bin/env bash
set -euo pipefail
cd /work
runid="$(date -u +%Y%m%dT%H%M%SZ)_cstr_fold_devcal_rtx5090"; out="results_raw/$runid"; mkdir -p "$out" build
nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xcompiler=-O3,-march=native,-DNDEBUG -o build/validate_cstr_folds src_cuda/validate_cstr_folds.cu >"$out/compile.log" 2>&1
for split in dev cal; do build/validate_cstr_folds --references references/cstr_fold_ref_v2_20260824 --split "$split" --out "$out" | tee -a "$out/run.log"; done
sha256sum references/cstr_fold_ref_v2_20260824/* src_cuda/validate_cstr_folds.cu >"$out/sha256.txt"
echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
