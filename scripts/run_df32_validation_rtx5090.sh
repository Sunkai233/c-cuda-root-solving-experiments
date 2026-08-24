#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_image="docker.m.daocloud.io/vllm/vllm-openai:latest"
runtime_image="nvidia/cuda:12.8.1-base-ubuntu24.04"
ref="references/ref_v1_20260824"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_df32_candidate_rtx5090"
out="results_raw/$run_id";mkdir -p "$root/build/cuda_strict" "$root/$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" \
  -lc 'set -o pipefail; nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-DNDEBUG -o build/cuda_strict/validate_df32 src_cuda/validate_df32.cu 2>&1 | tee build/cuda_strict/df32_compile.log'
for split in dev cal; do
  docker run --rm --gpus 'device=0' --entrypoint bash -v "$root:/work" -w /work "$runtime_image" \
    -lc "build/cuda_strict/validate_df32 --references '$ref' --out '$out' --split '$split'" | tee "$root/$out/${split}.log"
done
cp "$root/build/cuda_strict/df32_compile.log" "$root/$out/compile.log"
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,memory.total,compute_cap --format=csv > "$root/$out/hardware.txt"
sha256sum "$root/$ref"/*.csv "$root/include/df32.cuh" "$root/src_cuda/validate_df32.cu" > "$root/$out/sha256.txt"
printf '%s\n' "$run_id" > "$root/results_raw/LATEST_DF32_CANDIDATE"
echo "COMPLETE $run_id"
