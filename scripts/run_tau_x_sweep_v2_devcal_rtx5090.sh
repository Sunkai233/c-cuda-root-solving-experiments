#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_tau_x_sweep_v2_devcal_rtx5090";out="results_raw/$run_id";mkdir -p build/cuda_strict "$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work docker.m.daocloud.io/vllm/vllm-openai:latest -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/validate_tau src_cuda/validate_references.cu -lgomp' >"$out/compile.log" 2>&1
for tau in 1e-7 7.5e-8 5e-8 3e-8 1e-8;do for split in dev cal;do sub="$out/tau_${tau}_${split}";mkdir -p "$sub";docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/cuda_strict/validate_tau --references references/ref_v2_20260824 --out '$sub' --split '$split' --frozen-only --tau-x '$tau'" >"$sub/run.log";done;done
sha256sum references/ref_v2_20260824/*.csv src_cuda/benchmark.cu src_cuda/validate_references.cu >"$out/sha256.txt"
printf '%s\n' "$run_id" > results_raw/LATEST_TAU_X_SWEEP
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
