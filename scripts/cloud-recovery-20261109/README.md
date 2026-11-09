# Cloud installation recovery evidence (2026-11-09)

This directory preserves the small code, parameters and provenance used to verify the rebuilt CPU installation. The source at `d00a675aa6a379d91a5ab0329a2088420d7d19dd` is DVK's public `experimental` branch. TwoPunctures is the bundled `tpid` target, not a separate installation.

## What was tested

- `tpid`: a fresh symmetric q=1 solve at 12 x 12 x 12 spectral points, Newton residual 9.163643e-13. The 428,540-byte result has the expected serialization and all values are finite.
- `bssnSolver`: one RK4 step, maximum allowed depth 11. The adaptive mesh actually finished at levels 3 through 9. The checkpoint records step 1, t=0.06510416666666666, and 24 finite evolved fields at 702,157 nodes. Lapse and chi remain positive.
- CPU only, GNU 14, Open MPI 5.0.7, Release, FD6. No source edits were needed to compile. These tests establish that the programs run; they are not an accuracy or convergence study.

This is a **new installation test**, not recovery or continuation of the earlier lost evolution. No evolved checkpoint or VTU from the old run was reconstructed. Large smoke checkpoints, TP binary, executables, fetched dependencies and object files are deliberately excluded from Git.

## Reproduce the smoke test

After building `tpid` and `bssnSolver`, source any installation-specific library environment and run:

```bash
bash scripts/cloud-recovery-20261109/run-smoke.sh /absolute/path/to/build /absolute/path/to/output-parent
```

The script always creates a new unique directory. It uses one MPI rank and two OpenMP threads, bounds TP to 120 seconds and BSSN to 300 seconds, and validates serialized results instead of trusting exit status alone. The VM memory bound is 7 GiB. Increase the limits only deliberately on a slower or larger machine.

`source-pins.json` records the exact public source commits used. `dependency-packages.txt` and `dependency-sha256.txt` record the rootlessly extracted Debian trixie packages used alongside the system GCC/OpenMPI/BLAS/LAPACK runtimes. They do not imply portability of those binaries to a different distribution or CPU.

`q1-smoke.par.toml` derives from the retained q1 smoke parameters, with depth reduced to 11, VTU disabled, and a separate TP output prefix. `validation.json` contains the observed results, including the actual evolved time and per-field ranges. `validate_smoke.py` is the reusable checker.
