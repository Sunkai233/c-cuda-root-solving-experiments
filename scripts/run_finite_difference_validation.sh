set -euo pipefail
cd /home/abc/supplementary_experiments
run_id="$(date -u +%Y%m%dT%H%M%SZ)_finite_difference_cal"
out="results_raw/$run_id"
tmp_log="/tmp/$run_id.log"
docker run --rm --entrypoint python3 \
  --user "$(id -u):$(id -g)" \
  -v /home/abc/supplementary_experiments:/work -w /work \
  docker.m.daocloud.io/vllm/vllm-openai:latest \
  scripts/validate_finite_difference.py \
  --references references/ref_v1_20260824 \
  --out "$out" --split cal --dps 80 --workers 32 2>&1 | tee "$tmp_log"
mv "$tmp_log" "$out/run.log"
{
  uname -a
  lscpu | grep -E 'Model name|Socket|Core|Thread|CPU\(s\)'
  docker run --rm --entrypoint python3 docker.m.daocloud.io/vllm/vllm-openai:latest --version
  docker run --rm --entrypoint python3 docker.m.daocloud.io/vllm/vllm-openai:latest -c 'import mpmath; print("mpmath", mpmath.__version__)'
} > "$out/hardware.txt"
sha256sum scripts/validate_finite_difference.py references/ref_v1_20260824/*.csv \
  > "$out/sha256.txt"
echo "RUN_ID=$run_id"
