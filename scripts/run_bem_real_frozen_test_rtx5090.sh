#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";marker=manifests/TEST_SPLIT_EXECUTED_bem_real_adaptive_v1_20260824.txt
test ! -e "$marker" || { echo "test split already executed" >&2; exit 9; }
out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_frozen_test_rtx5090";mkdir -p "$out"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -Xptxas=-v -o build/benchmark_bem_real_frozen src_cuda/benchmark_bem_real.cu' > "$out/compile.log" 2>&1
printf 'started_utc=%s\nrun=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$out" > "$marker"
dataset=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/benchmark_bem_real_frozen '$dataset' 30 4 '$out/roots.bin' 10" | tee "$out/timing.json"
python3 scripts/analyze_bem_real_holdout.py --references references/bem_real_ref_v2_test_20260824/bem_real_reference.csv --roots "$out/roots.bin" --out "$out"
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.draw,clocks.sm,clocks.mem --format=csv > "$out/hardware.txt"
sha256sum manifests/frozen_bem_real_adaptive_v1.json references/bem_real_ref_v2_test_20260824/* include/bem_real_solver.h src_cuda/benchmark_bem_real.cu "$dataset" > "$out/sha256.txt"
printf 'completed_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$marker";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
