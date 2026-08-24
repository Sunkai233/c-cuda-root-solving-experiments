set -euo pipefail
cd /home/abc/supplementary_experiments
docker run --rm --entrypoint bash \
  -v /home/abc/supplementary_experiments:/work -w /work \
  docker.m.daocloud.io/vllm/vllm-openai:latest -lc '
    export PATH=/usr/local/cuda/bin:/usr/local/lib/python3.12/dist-packages/triton/backends/nvidia/bin:$PATH
    export NVDISASM_PATH=/usr/local/lib/python3.12/dist-packages/triton/backends/nvidia/bin/nvdisasm
    mkdir -p profiles
    cuobjdump --dump-sass build/cuda_strict/performance_df32 > /tmp/all.sass
    awk "/Function : _Z11kernel_df32PK6DParamP7DOutputm/{f=1;next} /Function :/{if(f)exit} f" \
      /tmp/all.sass > /tmp/df32.sass
    {
      echo "binary=build/cuda_strict/performance_df32"
      echo "kernel=_Z11kernel_df32PK6DParamP7DOutputm"
      echo "sass_lines=$(wc -l < /tmp/df32.sass)"
      for op in DADD DMUL DFMA DSETP; do
        echo "$op=$(grep -c "$op" /tmp/df32.sass || true)"
      done
      for op in FADD FMUL FFMA FSETP MUFU; do
        echo "$op=$(grep -c "$op" /tmp/df32.sass || true)"
      done
    } | tee profiles/df32_sass_audit.txt
    forbidden=$(grep -Ec "DADD|DMUL|DFMA|DSETP" /tmp/df32.sass || true)
    test "$forbidden" -eq 0
  '
