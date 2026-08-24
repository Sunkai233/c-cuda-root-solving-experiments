#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_validation_v2_devcal_rtx5090";out="results_raw/$run_id"
mkdir -p build/cuda_strict "$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work docker.m.daocloud.io/vllm/vllm-openai:latest -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/validate_raw src_cuda/validate_references.cu -lgomp' >"$out/compile.log" 2>&1
for split in dev cal;do docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/cuda_strict/validate_raw --references references/ref_v2_20260824 --out '$out' --split '$split' --frozen-only" | tee "$out/$split.log";done
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total,compute_cap --format=csv >"$out/hardware.txt"
sha256sum references/ref_v2_20260824/*.csv references/ref_v2_20260824/manifest.json src_cuda/benchmark.cu src_cuda/validate_references.cu >"$out/sha256.txt"
printf '%s\n' "$run_id" > results_raw/LATEST_VALIDATION_V2_DEVCAL
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
