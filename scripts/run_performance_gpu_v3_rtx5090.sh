#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_performance_gpu_v3_rtx5090";mkdir -p "$out";echo "$out" > results_raw/LATEST_PERFORMANCE_GPU_V3
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.mem --format=csv > "$out/hardware_before.csv"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/performance_gpu_v3 src_cuda/performance_matrix.cu -lgomp' > "$out/compile.log" 2>&1
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/performance_gpu_v3 --out '$out' --max-n 16777216 --repetitions 30 --warmups 10 --heat-seconds 45 --tau-x 3e-8 --skip-cpu" | tee "$out/run.log"
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.mem --format=csv > "$out/hardware_after.csv"
sha256sum manifests/frozen_adaptive_v3.json src_cuda/benchmark.cu src_cuda/performance_matrix.cu > "$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
