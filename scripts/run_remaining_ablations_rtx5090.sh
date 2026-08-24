#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_remaining_ablations_rtx5090";mkdir -p "$out" build
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -o build/remaining_ablations src_cuda/benchmark_remaining_ablations.cu' >"$out/compile.log" 2>&1
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/remaining_ablations --out '$out' --n 3342336" | tee "$out/run.log"
sha256sum src_cuda/benchmark_remaining_ablations.cu >"$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
