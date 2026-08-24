#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_image="docker.m.daocloud.io/vllm/vllm-openai:latest";runtime_image="nvidia/cuda:12.8.1-base-ubuntu24.04"
mode="${1:-smoke}";if [ "$mode" = full ];then maxn=16777216;reps=30;warm=10;heat=45;else maxn=32768;reps=3;warm=2;heat=1;fi
run_id="$(date -u +%Y%m%dT%H%M%SZ)_performance_${mode}_rtx5090";out="results_raw/$run_id";mkdir -p "$root/build/cuda_strict" "$root/$out"
{ nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total,compute_cap --format=csv;lscpu|grep -E 'Model name|Socket|Core|Thread|NUMA'; } > "$root/$out/hardware_before.txt"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$build_image" -lc 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xptxas=-v -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_strict/performance src_cuda/performance_matrix.cu -lgomp 2>&1 | tee build/cuda_strict/performance_compile.log'
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work -v /usr/lib/x86_64-linux-gnu/libgomp.so.1:/usr/lib/x86_64-linux-gnu/libgomp.so.1:ro "$runtime_image" -lc "build/cuda_strict/performance --out '$out' --max-n '$maxn' --repetitions '$reps' --warmups '$warm' --heat-seconds '$heat'" | tee "$root/$out/run.log"
cp "$root/build/cuda_strict/performance_compile.log" "$root/$out/compile.log";nvidia-smi --query-gpu=name,temperature.gpu,power.draw,clocks.sm,clocks.mem --format=csv > "$root/$out/hardware_after.txt";sha256sum "$root/src_cuda/benchmark.cu" "$root/src_cuda/performance_matrix.cu" "$root/manifests/frozen_adaptive_v1.json" > "$root/$out/sha256.txt";echo "$run_id" > "$root/results_raw/LATEST_PERFORMANCE_${mode^^}";echo "COMPLETE $run_id"
