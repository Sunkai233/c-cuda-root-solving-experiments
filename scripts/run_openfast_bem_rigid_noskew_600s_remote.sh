#!/usr/bin/env bash
set -euo pipefail

root=/home/abc/supplementary_experiments
src="$root/domains/bem/openfast/5MW_Land_600s_rigid"
dst="$root/domains/bem/openfast/5MW_Land_600s_rigid_noskew"
openfast="$root/_deps/openfast_3a9d3f2/build_release/glue-codes/openfast/openfast"
run_dir="$root/results_raw/20260824T055000Z_openfast_bem_rigid_noskew"

test ! -e "$dst"
mkdir -p "$dst"
cp "$src/5MW_600s_alpha.fst" "$dst/"
cp "$src/NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat" "$dst/"
cp "$src/NRELOffshrBsline5MW_Onshore_ElastoDyn.dat" "$dst/"
cp "$src/NRELOffshrBsline5MW_Onshore_ElastoDyn_Tower.dat" "$dst/"
cp "$src/NRELOffshrBsline5MW_Onshore_ServoDyn.dat" "$dst/"
sed -i -E 's/^1([[:space:]]+Skew_Mod)/0\1/' \
  "$dst/NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat"
grep 'Skew_Mod' "$dst/NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat"

cd "$dst"
start="$(date -u +%FT%TZ)"
"$openfast" 5MW_600s_alpha.fst > openfast_600s_rigid_noskew.log 2>&1
end="$(date -u +%FT%TZ)"
grep -q 'OpenFAST terminated normally' openfast_600s_rigid_noskew.log
{
  echo "source_commit=3a9d3f2"
  echo "case=rigid_blade_noskew_with_internal_bem_diagnostics"
  echo "start_utc=$start"
  echo "end_utc=$end"
  echo "ordinary_root_instances=2448000"
  sha256sum 5MW_600s_alpha.fst NRELOffshrBsline5MW_Onshore_AeroDyn_noUA_debug.dat \
    NRELOffshrBsline5MW_Onshore_ElastoDyn.dat 5MW_600s_alpha.outb
  stat -c 'outb_bytes=%s' 5MW_600s_alpha.outb
  grep -E 'Total Real Time|Simulation CPU Time|Simulated Time|Time Ratio' openfast_600s_rigid_noskew.log
} | tee openfast_600s_rigid_noskew_manifest.txt

"/home/abc/miniconda3/envs/of/bin/python" "$root/scripts/analyze_openfast_bem.py" \
  --outb "$dst/5MW_600s_alpha.outb" \
  --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" \
  --out "$run_dir"
"/home/abc/miniconda3/envs/of/bin/python" "$root/scripts/validate_openfast_legacy_residual.py" \
  --outb "$dst/5MW_600s_alpha.outb" \
  --blade "$root/domains/bem/openfast/5MW_Baseline/NRELOffshrBsline5MW_AeroDyn_blade.dat" \
  --openfast-io "$root/_deps/openfast_3a9d3f2/openfast_io" \
  --out "$run_dir/openfast_residual_audit.json"
cp openfast_600s_rigid_noskew.log openfast_600s_rigid_noskew_manifest.txt "$run_dir/"
