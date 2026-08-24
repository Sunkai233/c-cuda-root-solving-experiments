#!/usr/bin/env bash
set -euo pipefail
root=/home/abc/supplementary_experiments
cd "$root"
image=nvidia/cuda:12.8.1-devel-ubuntu24.04
mkdir -p build/cuda_profile profiles
docker run --rm --gpus all --entrypoint bash -v "$root:/work" -w /work "$image" -lc \
  'nvcc -std=c++17 -O3 -lineinfo -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Xcompiler=-O3,-march=native,-fopenmp,-DNDEBUG -o build/cuda_profile/profile_driver src_cuda/profile_driver.cu -lgomp && nvcc -std=c++17 -O3 -lineinfo -arch=sm_120 --fmad=true --ftz=false --prec-div=true --prec-sqrt=true -Iinclude -o build/cuda_profile/benchmark_bem_real src_cuda/benchmark_bem_real.cu'
for domain in 0 1 2 3 4;do
  name="profiles/adaptive_domain${domain}_n131072"
  test -f "$name.ncu-rep" || docker run --rm --gpus device=0 --cap-add SYS_ADMIN --entrypoint bash \
    -v "$root:/work" -w /work "$image" -lc \
    "ncu --set full --kernel-name regex:kernel_adaptive --force-overwrite --export '$name' build/cuda_profile/profile_driver '$domain' 2 131072"
done
dataset=results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin
for algorithm in 0 3;do
  name="profiles/bem_real_algorithm${algorithm}"
  test -f "$name.ncu-rep" || docker run --rm --gpus device=0 --cap-add SYS_ADMIN --entrypoint bash \
    -v "$root:/work" -w /work "$image" -lc \
    "ncu --set full --kernel-name regex:solve_kernel --launch-skip 2 --launch-count 1 --force-overwrite --export '$name' build/cuda_profile/benchmark_bem_real '$dataset' 1 '$algorithm'"
done
docker run --rm --entrypoint bash -v "$root:/work" "$image" -lc \
  'chown -R 1000:1000 /work/profiles'
for report in profiles/adaptive_domain*_n131072.ncu-rep profiles/bem_real_algorithm*.ncu-rep;do
  docker run --rm --entrypoint bash -v "$root:/work" -w /work "$image" -lc \
    "ncu --import '$report' --page raw --csv" > "${report%.ncu-rep}.csv"
done
sha256sum profiles/*.ncu-rep profiles/*.csv > profiles/sha256.txt
