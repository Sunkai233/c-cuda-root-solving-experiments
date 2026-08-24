#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_power_trace_rtx5090";mkdir -p "$out"
query=timestamp,index,name,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.mem,utilization.gpu
nvidia-smi --query-gpu="$query" --format=csv -lms 200 > "$out/power_thermal_trace.csv" & sampler=$!
trap 'kill "$sampler" 2>/dev/null || true; wait "$sampler" 2>/dev/null || true' EXIT
dataset=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/benchmark_bem_real_frozen '$dataset' 240 4 /tmp/bem_power_roots.bin 120" > "$out/timing.json"
kill "$sampler" 2>/dev/null || true;wait "$sampler" 2>/dev/null || true;trap - EXIT
sha256sum manifests/frozen_bem_real_adaptive_v1.json include/bem_real_solver.h src_cuda/benchmark_bem_real.cu "$dataset" > "$out/sha256.txt"
echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
