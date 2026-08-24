#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root"
config_id=adaptive_v2_20260824
candidate_commit=1fa526aab65f287db1f10ffbfd3188a51a14eca7
marker="manifests/TEST_SPLIT_EXECUTED_${config_id}.txt"
if [[ -e "$marker" ]];then echo "REFUSING: frozen test already executed: $marker" >&2;exit 9;fi
printf '%s  %s\n' 649cfcbefa0ab65e727c8208835032a389f51f8488fafcda4e91fabd4f0696a9 src_cuda/benchmark.cu \
  4cfbee4dd3252be141d4fe5b92bdbf0f009789d5dcb25a242c7dbec9ca568e1e src_cuda/validate_references.cu \
  884adf3d95a64d1406d3e4a81f20d3cfb900c1dfa0b21e49f7f08747c1251f3a manifests/frozen_adaptive_v2.json | sha256sum -c -
run_id="$(date -u +%Y%m%dT%H%M%SZ)_frozen_test_v2_rtx5090";out="results_raw/$run_id";mkdir -p build/cuda_strict "$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work docker.m.daocloud.io/vllm/vllm-openai:latest -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/validate_raw src_cuda/validate_references.cu -lgomp' >"$out/compile.log" 2>&1
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/cuda_strict/validate_raw --references references/ref_v2_20260824 --out '$out' --split test --frozen-only" | tee "$out/test.log"
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total,compute_cap --format=csv >"$out/hardware.txt"
sha256sum references/ref_v2_20260824/*.csv references/ref_v2_20260824/manifest.json manifests/frozen_adaptive_v2.json src_cuda/benchmark.cu src_cuda/validate_references.cu >"$out/sha256.txt"
{
  printf 'config_id=%s\n' "$config_id"
  printf 'candidate_commit=%s\n' "$candidate_commit"
  printf 'run_id=%s\n' "$run_id"
  printf 'executed_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'policy=single frozen test execution; do not rerun\n'
} | tee "$marker" >"$out/frozen_marker.txt"
printf '%s\n' "$run_id" > results_raw/LATEST_FROZEN_TEST_V2
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
