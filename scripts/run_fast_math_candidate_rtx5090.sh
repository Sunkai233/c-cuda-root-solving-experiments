#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_image="docker.m.daocloud.io/vllm/vllm-openai:latest"
runtime_image="nvidia/cuda:12.8.1-base-ubuntu24.04"
ref="references/ref_v1_20260824"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_fast_math_candidate_rtx5090"
out="results_raw/$run_id"

mkdir -p "$root/build/cuda_fast" "$root/$out"

docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" \
  -lc 'nvcc -std=c++17 -O3 -arch=sm_120 --use_fast_math -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_fast/validate src_cuda/validate_references.cu -lgomp 2>&1 | tee build/cuda_fast/validate_compile.log'

for split in dev cal; do
  docker run --rm --gpus 'device=0' --entrypoint bash -v "$root:/work" -w /work \
    -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro "$runtime_image" \
    -lc "build/cuda_fast/validate --references '$ref' --out '$out' --split '$split' --frozen-only" \
    | tee "$root/$out/${split}.log"
done

cp "$root/build/cuda_fast/validate_compile.log" "$root/$out/compile.log"
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total,compute_cap --format=csv > "$root/$out/hardware.txt"
sha256sum "$root/$ref"/*.csv "$root/manifests/frozen_adaptive_v1.json" \
  "$root/src_cuda/benchmark.cu" "$root/src_cuda/validate_references.cu" > "$root/$out/sha256.txt"
cat > "$root/$out/manifest.json" <<EOF
{
  "run_id": "$run_id",
  "status": "candidate_only",
  "build": "cuda_fast_math",
  "compile_flags": "-O3 -arch=sm_120 --use_fast_math",
  "splits": ["dev", "cal"],
  "test_split_executed": false,
  "note": "Post-freeze secondary candidate; not a replacement for the one-shot strict test."
}
EOF
printf '%s\n' "$run_id" > "$root/results_raw/LATEST_FAST_MATH_CANDIDATE"
echo "COMPLETE $run_id"
