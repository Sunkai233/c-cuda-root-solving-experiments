#!/usr/bin/env bash
set -euo pipefail
cd /home/abc/supplementary_experiments
mkdir -p build/cuda_strict results_raw/smoke_validation_raw
docker run --rm --gpus all --entrypoint bash -v /home/abc/supplementary_experiments:/work -w /work docker.m.daocloud.io/vllm/vllm-openai:latest -lc \
  'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/validate_raw src_cuda/validate_references.cu -lgomp'
docker run --rm --gpus all --entrypoint bash -v /home/abc/supplementary_experiments:/work -w /work -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  'build/cuda_strict/validate_raw --references references/ref_v1_20260824 --out results_raw/smoke_validation_raw --split cal --frozen-only'
wc -l results_raw/smoke_validation_raw/validation_cal_raw.csv
