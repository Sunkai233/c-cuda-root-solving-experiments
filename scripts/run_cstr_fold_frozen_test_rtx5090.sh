#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments; cd "$root"
marker=manifests/TEST_SPLIT_EXECUTED_cstr_fold_v1_20260824.txt
test ! -e "$marker" || { echo "CSTR fold test already executed" >&2; exit 9; }
out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_cstr_fold_frozen_test_rtx5090"; mkdir -p "$out"
printf 'started_utc=%s\nrun=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$out" >"$marker"
docker run --rm --gpus device=0 -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 \
  build/validate_cstr_folds --references references/cstr_fold_ref_v2_20260824 --split test --out "$out" | tee "$out/run.log"
python3 - "$out/cstr_fold_test_summary.csv" <<'PY'
import csv,sys
r=next(csv.DictReader(open(sys.argv[1])))
limits={'root_max':1e-10,'gradient_max':5e-7,'condition_max':5e-7,'regularized_max':5e-7,'continuation_root_max':1e-12}
for k,v in limits.items():
    assert float(r[k]) <= v,(k,r[k],v)
for k in ('wrong_branch_or_count','nonfinite','continuation_wrong','ambiguous_wrong'):
    assert int(r[k]) == 0,(k,r[k])
PY
sha256sum manifests/frozen_cstr_fold_v1.json references/cstr_fold_ref_v2_20260824/* src_cuda/validate_cstr_folds.cu >"$out/sha256.txt"
printf 'completed_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$marker"
echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
