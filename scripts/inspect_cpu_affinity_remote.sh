#!/usr/bin/env bash
set -euo pipefail
taskset -pc $$
numactl --hardware
lscpu -e=CPU,NODE,SOCKET,CORE,ONLINE | head -40
