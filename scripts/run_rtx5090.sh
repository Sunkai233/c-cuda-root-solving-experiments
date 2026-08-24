#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_image="docker.m.daocloud.io/vllm/vllm-openai:latest"
runtime_image="nvidia/cuda:12.8.1-base-ubuntu24.04"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_all_rtx5090_adaptive"
out="$root/results_raw/$run_id"
mkdir -p "$root/build/cuda_strict" "$root/build/cuda_fast" "$out"

{
  echo "run_id=$run_id"
  echo "source_sha256=$(sha256sum "$root/src_cuda/benchmark.cu" | awk '{print $1}')"
  echo "git_commit=$(git -C "$root" rev-parse HEAD 2>/dev/null || echo uncommitted)"
  lscpu | grep -E 'Model name|Socket|Core|Thread|NUMA'
  nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total,compute_cap --format=csv
} > "$out/manifest.txt"

docker run --rm --gpus all --entrypoint bash \
  -v "$root:/work" -w /work "$build_image" \
  -lc 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/solver src_cuda/benchmark.cu -lgomp 2>&1 | tee build/cuda_strict/compile.log'

docker run --rm --gpus all --entrypoint bash \
  -v "$root:/work" -w /work \
  -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro \
  "$runtime_image" \
  -lc 'build/cuda_strict/solver --out '"results_raw/$run_id"' --max-n 16777216 --repetitions 30 --warmups 10 | tee '"results_raw/$run_id/run.log"''

echo "$run_id" > "$root/results_raw/LATEST"
echo "COMPLETE $run_id"
