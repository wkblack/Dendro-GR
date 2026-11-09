# Recovery-kit validation, 2026-11-09

Passed:

- Bash syntax checks for setup.sh and snapshot.sh; Python compilation check.
- Nine offline safety tests using disposable local Git fixtures: repeatable
  pinned checkout with preserved branch history; refusal of dirty source,
  nonempty unrelated prefixes, changed settings and settings symlinks;
  side-effect-free plan; credential-free URL checks; exact-tree fallback success
  and mismatch rejection. `tests/offline-test-results.txt` contains the results.
- A new isolated prefix restored pynwave2d from the included full Git bundle,
  applied the recorded repair, created a new Python 3.12 venv, and installed all
  exact dependencies from PyPI. `pip check`, imports, and all four scientific
  boundary regression tests passed.
- A second full Python setup invocation on the same prefix passed, reusing the
  pinned checkout/venv. No duplicated patch or unwanted branch movement.
- `git bundle verify` passed for the complete pynwave history bundle. It contains
  the original branches and the three newly archived work snapshots.
- A separate clean Dendro prefix successfully extracted all checksum-verified
  Debian packages, linked the compatible preinstalled MPI runtime, and configured
  CMake with all five sources pinned and FetchContent network access disabled.
  Both tpid and bssnSolver then compiled successfully at two build jobs; ldd
  confirmed no unresolved dynamic libraries. For this build, source repos and
  package archives were supplied from verified local caches.
- An additional fresh-prefix end-to-end `--deps local-apt --checkout-only` run
  downloaded signed Debian metadata and all 13 exact package archives, checked
  every SHA256, extracted/configured the local toolchain, and restored pynwave
  source from the bundle. Thus the rootless apt network path was exercised too.
  It needed no administrator access and did not run package installation scripts.

- Finally, the newly rebuilt binaries passed the included bounded TPID + BSSN
  smoke script in another new output directory: both exits were zero, TPID's
  final Newton residual was 9.163643e-13, and BSSN completed step 1 at time
  0.0651041666667 with all 24 fields finite across 702,157 nodes. The fresh result
  is retained as `tests/dendro-rebuilt-smoke.json`. This validates the kit build,
  not only the earlier independently restored binaries.

The first isolated Dendro configure exposed missing MPI runtime link handling;
the recipe was repaired before the passing clean rebuild. This is why actual
fresh-prefix testing was performed rather than only copying shell commands.

Separately verified original restoration:

- A bounded 12-cubed TwoPunctures solve and one-step BSSN smoke run passed,
  including finite TPID serialization and all 24 evolved checkpoint fields.
  The exact test recipe and original numeric output are included under
  examples/dendro-smoke/. These results precede the second kit rebuild.

Not claimed:

- Fresh remote GitHub acquisition has not been retested through this kit.
  The original restoration acquired those public sources successfully, and all
  16 pynwave backup ref heads and source trees were separately verified.
- System-wide --deps apt installation, other distributions, macOS, Windows,
  alternate Python versions, and different CPU architectures are untested.
- Python wheels are version-pinned, not hash-locked or vendored. Debian live
  mirrors and public GitHub availability remain external dependencies.
- No convergence, long-evolution validity, or restoration of old simulation
  output/checkpoints is implied by these installation tests.
