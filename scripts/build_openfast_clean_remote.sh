#!/usr/bin/env bash
set -euo pipefail

# Reproduces the clean OpenFAST/TurbSim build used on abc66.  The source archive
# is a `git archive` of local OpenFAST commit 3a9d3f2 and deliberately contains
# no working-tree modifications or .git directory.
root=/home/abc/supplementary_experiments
deps="$root/_deps"
src="$deps/openfast_3a9d3f2"
build="$src/build_release"

cd "$deps"
if [[ ! -f "$src/CMakeLists.txt" ]]; then
  mkdir -p "$src"
  tar -xzf openfast_clean_3a9d3f2.tar.gz -C "$src"
fi

cmake -S "$src" -B "$build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF \
  -DBUILD_FASTFARM=OFF \
  -DBUILD_OPENFAST_CPP_API=OFF \
  -DUSE_LOCAL_STATIC_LAPACK=ON
cmake --build "$build" --target openfast turbsim -j 32

"$build/glue-codes/openfast/openfast" -v
"$build/modules/turbsim/turbsim" -v || true
