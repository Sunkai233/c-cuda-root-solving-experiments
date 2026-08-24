#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";marker=manifests/TEST_SPLIT_EXECUTED_bem_real_gradient_v1_20260824.txt
test ! -e "$marker" || { echo "gradient test already executed" >&2; exit 9; };out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_gradient_frozen_test_rtx5090";mkdir -p "$out"
printf 'started_utc=%s\nrun=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$out" > "$marker"
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/validate_bem_real_gradients --references references/bem_real_ref_v2_test_20260824/bem_real_reference.csv --split test --out '$out'" | tee "$out/run.log"
sha256sum manifests/frozen_bem_real_gradient_v1.json references/bem_real_ref_v2_test_20260824/* include/bem_real_solver.h src_cuda/validate_bem_real_gradients.cu > "$out/sha256.txt"
printf 'completed_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$marker";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
