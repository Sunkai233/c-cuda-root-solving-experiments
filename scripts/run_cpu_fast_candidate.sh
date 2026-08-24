#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
cd "$root"
if find /sys/devices/system/cpu/cpufreq -name scaling_governor -type f -exec cat {} \; 2>/dev/null | grep -vxq performance; then
  echo "all governors must be performance" >&2
  exit 4
fi
strict_run="$(cat results_raw/LATEST_CPU_C17)"
test -f "results_raw/$strict_run/COMPLETE.txt"
run_id="$(date -u +%Y%m%dT%H%M%SZ)_cpu_fast_candidate"
out="results_raw/$run_id"
mkdir -p "$out/strict_validation" "$out/fast_validation" "$out/nolto_validation" \
  build/cpu_fast build/cpu_strict build/cpu_nolto
strict_flags=(-std=c17 -O3 -march=native -mtune=native -flto -fopenmp -DNDEBUG
  -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic -Wshadow -Wconversion)
gcc "${strict_flags[@]}" src_cpu/validate_cpu_references.c -lm \
  -o build/cpu_strict/validate_cpu_references 2>"$out/strict_validation_compile.log"
gcc -std=c17 -O3 -march=native -mtune=native -fopenmp -DNDEBUG \
  -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic -Wshadow -Wconversion \
  src_cpu/benchmark_cpu.c -lm -o build/cpu_nolto/benchmark_cpu 2>"$out/nolto_compile.log"
gcc -std=c17 -O3 -march=native -mtune=native -fopenmp -DNDEBUG \
  -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic -Wshadow -Wconversion \
  src_cpu/validate_cpu_references.c -lm -o build/cpu_nolto/validate_cpu_references \
  2>"$out/nolto_validation_compile.log"
gcc -std=c17 -O3 -march=native -mtune=native -flto -fopenmp -DNDEBUG \
  -ffast-math -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic \
  -Wshadow -Wconversion src_cpu/benchmark_cpu.c -lm \
  -o build/cpu_fast/benchmark_cpu 2>"$out/compile.log"
gcc -std=c17 -O3 -march=native -mtune=native -flto -fopenmp -DNDEBUG \
  -ffast-math -fno-math-errno -fno-trapping-math -Wall -Wextra -Wpedantic \
  -Wshadow -Wconversion src_cpu/validate_cpu_references.c -lm \
  -o build/cpu_fast/validate_cpu_references 2>"$out/fast_validation_compile.log"
for split in dev cal test; do
  taskset -c 0 build/cpu_strict/validate_cpu_references references/ref_v3_20260824 \
    "$split" "$out/strict_validation" | tee -a "$out/strict_validation.log"
done
if taskset -c 0 build/cpu_nolto/validate_cpu_references references/ref_v3_20260824 test \
    "$out/nolto_validation" | tee "$out/nolto_validation.log"; then
  printf 'NO_LTO_TEST_PASS\n' >"$out/NO_LTO_STATUS.txt"
else
  printf 'NO_LTO_TEST_FAIL\n' >"$out/NO_LTO_STATUS.txt"
fi
fast_ok=1
for split in dev cal; do
  if ! taskset -c 0 build/cpu_fast/validate_cpu_references references/ref_v3_20260824 \
      "$split" "$out/fast_validation" | tee -a "$out/fast_validation.log"; then fast_ok=0; fi
done
if (( fast_ok )); then
  if taskset -c 0 build/cpu_fast/validate_cpu_references references/ref_v3_20260824 \
      test "$out/fast_validation" | tee -a "$out/fast_validation.log"; then
    printf 'FAST_CANDIDATE_TEST_PASS\n' >"$out/FAST_STATUS.txt"
  else
    printf 'FAST_CANDIDATE_TEST_FAIL\n' >"$out/FAST_STATUS.txt"
  fi
else
  printf 'FAST_CANDIDATE_REJECTED_DEV_CAL_TEST_NOT_TOUCHED\n' >"$out/FAST_STATUS.txt"
fi
OMP_PROC_BIND=close OMP_PLACES=cores numactl --physcpubind=0-95 --membind=0 \
  build/cpu_fast/benchmark_cpu "$out/fast_omp96.csv" 16777216 30 10 96 2 \
  >"$out/fast_omp96.log"
OMP_PROC_BIND=close OMP_PLACES=cores numactl --physcpubind=0-95 --membind=0 \
  build/cpu_nolto/benchmark_cpu "$out/strict_nolto_omp96.csv" 16777216 30 10 96 2 \
  >"$out/strict_nolto_omp96.log"
{
  printf 'run_id=%s\nstrict_comparator_run=%s\n' "$run_id" "$strict_run"
  printf 'threads=96\naffinity=physical_cpus_0-95\nnuma_node=0\n'
  printf 'flags=-std=c17 -O3 -march=native -mtune=native -flto -fopenmp -DNDEBUG -ffast-math\n'
  gcc --version | head -1
} >"$out/manifest.txt"
sha256sum src_cpu/benchmark_cpu.c src_cpu/validate_cpu_references.c references/ref_v3_20260824/* \
  "results_raw/$strict_run/strict_omp96.csv" \
  "$out/fast_omp96.csv" "$out/strict_nolto_omp96.csv" >"$out/sha256.txt"
printf 'COMPLETE %s\n' "$run_id" | tee "$out/COMPLETE.txt"
