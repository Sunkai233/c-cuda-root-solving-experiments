#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";config_id=adaptive_v3_20260824;candidate_commit=77e970d4255b22aa153597fad3675bb20e433cf8;tau=3e-8
marker="manifests/TEST_SPLIT_EXECUTED_${config_id}.txt";if [[ -e "$marker" ]];then echo "REFUSING: frozen test already executed: $marker" >&2;exit 9;fi
printf '%s  %s\n' 649cfcbefa0ab65e727c8208835032a389f51f8488fafcda4e91fabd4f0696a9 src_cuda/benchmark.cu \
  df7f45e978d08d0a55ff29c6efa4bff014a77a538271d98dd7acefc445a4f544 src_cuda/validate_references.cu \
  abf77f08c6d2d92ca0cda40abf85e14734a0343bb29141879c3336d02f1b83a1 manifests/frozen_adaptive_v3.json | sha256sum -c -
run_id="$(date -u +%Y%m%dT%H%M%SZ)_frozen_test_v3_rtx5090";out="results_raw/$run_id";mkdir -p build/cuda_strict "$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work docker.m.daocloud.io/vllm/vllm-openai:latest -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/validate_raw src_cuda/validate_references.cu -lgomp' >"$out/compile.log" 2>&1
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/cuda_strict/validate_raw --references references/ref_v3_20260824 --out '$out' --split test --frozen-only --tau-x '$tau'" | tee "$out/test.log"
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total,compute_cap --format=csv >"$out/hardware.txt"
sha256sum references/ref_v3_20260824/*.csv references/ref_v3_20260824/manifest.json manifests/frozen_adaptive_v3.json src_cuda/benchmark.cu src_cuda/validate_references.cu >"$out/sha256.txt"
printf 'config_id=%s\ncandidate_commit=%s\nrun_id=%s\nexecuted_utc=%s\npolicy=single frozen test execution; do not rerun\n' "$config_id" "$candidate_commit" "$run_id" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$marker" >"$out/frozen_marker.txt"
printf '%s\n' "$run_id" >results_raw/LATEST_FROZEN_TEST_V3;printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
