#!/usr/bin/env bash
set -euo pipefail
# Source the installation environment before this script if libraries are local.
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
build=$(realpath "${1:?Usage: run-smoke.sh BUILD_DIR [OUTPUT_PARENT]}")
parent=$(realpath "${2:-.}")
run=$(mktemp -d "$parent/dendro-installation-smoke.XXXXXX")
mkdir -p "$run/"{vtu,cp,dat}
cp "$here/q1-smoke.par.toml" "$run/"
cd "$run"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
set +e
(ulimit -v 7340032; ulimit -t 120; timeout --kill-after=5s 120 "$build/BSSN_GR/tpid" q1-smoke.par.toml 2) > tpid.log 2>&1
rc=$?; printf '%s\n' "$rc" > tpid.exit
set -e
if ((rc)); then cat tpid.log; exit "$rc"; fi
python3 "$here/validate_smoke.py" . > validation-tpid.json
set +e
(ulimit -v 7340032; ulimit -t 300; timeout --kill-after=10s 300 "$build/BSSN_GR/bssnSolver" q1-smoke.par.toml 1) > bssn.log 2>&1
rc=$?; printf '%s\n' "$rc" > bssn.exit
set -e
if ((rc)); then cat bssn.log; exit "$rc"; fi
python3 "$here/validate_smoke.py" . > validation.json
cat validation.json
printf '\nSmoke evidence: %s\n' "$run"
