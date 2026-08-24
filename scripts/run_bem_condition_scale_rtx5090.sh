#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments;cd "$root";inputs=results_raw/20260824T_bem_condition_scale_inputs_v1
out="results_raw/$(date -u +%Y%m%dT%H%M%SZ)_bem_condition_scale_rtx5090";mkdir -p "$out"
python3 - "$inputs" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);m=json.loads((p/'manifest.json').read_text())
for name,want in m['files_sha256'].items():
 got=hashlib.sha256((p/name).read_bytes()).hexdigest()
 if got!=want:raise SystemExit(f'hash mismatch: {name}')
print(f"verified {len(m['files_sha256'])} input hashes")
PY
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-devel-ubuntu24.04 -lc \
 'nvcc -std=c++17 -O3 -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -Xptxas=-v -o build/benchmark_bem_real_scale src_cuda/benchmark_bem_real.cu' > "$out/compile.log" 2>&1
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.draw,clocks.sm,clocks.mem --format=csv > "$out/hardware_before.csv"
for dataset in "$inputs"/mixed_*.bin "$inputs"/*_524288.bin;do
 name="$(basename "$dataset" .bin)";docker run --rm --gpus device=0 --entrypoint bash -v "$root:/work" -w /work nvidia/cuda:12.8.1-base-ubuntu24.04 -lc \
  "build/benchmark_bem_real_scale '${dataset#"$root/"}' 30 4 /tmp/${name}_roots.bin 10" > "$out/$name.json"
done
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.draw,clocks.sm,clocks.mem --format=csv > "$out/hardware_after.csv"
sha256sum "$inputs/manifest.json" include/bem_real_solver.h src_cuda/benchmark_bem_real.cu > "$out/sha256.txt";echo "COMPLETE $out" | tee "$out/COMPLETE.txt"
