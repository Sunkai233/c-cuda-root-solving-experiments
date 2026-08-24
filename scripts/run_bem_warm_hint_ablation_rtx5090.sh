#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";inputs=results_raw/20260824T_bem_condition_scale_inputs_v3
out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_warm_hint_ablation_rtx5090";mkdir -p "$out" "$inputs/warm"
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/prepare_bem_warm_hints src_cuda/prepare_bem_warm_hints.cu'
for cold in "$inputs"/*_524280.bin;do
 name="$(basename "$cold" .bin)";warm="$inputs/warm/${name}_warm.bin"
 docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/prepare_bem_warm_hints '${cold#"$root/"}' '${warm#"$root/"}'" > "$out/${name}_prepare.log"
 for mode in cold warm;do dataset="$cold";test "$mode" = cold || dataset="$warm";docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/benchmark_bem_real_scale '${dataset#"$root/"}' 30 4 /tmp/${name}_${mode}_roots.bin 10" > "$out/${name}_${mode}.json";done
done
sha256sum "$inputs"/*_524280.bin "$inputs"/warm/*.bin include/bem_real_solver.h src_cuda/prepare_bem_warm_hints.cu src_cuda/benchmark_bem_real.cu > "$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
