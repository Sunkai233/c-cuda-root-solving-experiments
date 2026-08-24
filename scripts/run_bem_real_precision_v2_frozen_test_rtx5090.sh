#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";marker=manifests/TEST_SPLIT_EXECUTED_bem_real_precision_v2_20260824.txt
test ! -e "$marker" || { echo "BEM precision v2 test already executed" >&2;exit 9; };out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_real_precision_v2_frozen_test_rtx5090";mkdir -p "$out"
printf 'started_utc=%s\nrun=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$out" >"$marker"
docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
 "build/validate_bem_real_precision --references references/bem_real_ref_v4_df32_adaptive_test_20260824/bem_real_reference.csv --split test --out '$out'" | tee "$out/run.log"
python3 - "$out/bem_precision_test_summary.csv" <<'PY'
import csv,sys
r={x['method']:x for x in csv.DictReader(open(sys.argv[1]))};m=r['df32_adaptive']
assert float(m['root_max'])<=1e-7,m['root_max']
assert int(m['wrong_branch_gt_1e-3'])==0 and int(m['nonfinite'])==0,m
PY
sha256sum manifests/frozen_bem_real_precision_v2.json references/bem_real_ref_v4_df32_adaptive_test_20260824/* include/bem_real_precision.cuh include/df32.cuh src_cuda/validate_bem_real_precision.cu >"$out/sha256.txt"
printf 'completed_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$marker";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
