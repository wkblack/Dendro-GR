# Recovery-kit validation, 2026-11-09

Passed:

- Bash syntax checks for setup.sh and snapshot.sh; Python compilation check.
- Nine offline safety tests using disposable local Git fixtures: idempotent
  clone/pin, preservation of branches, refusal of dirty source, nonempty-prefix
  protection, edited-settings protection, symlink-settings protection,
  side-effect-free plan, credential-free URL validation, and fallback source
  tree verification (two cases share broader categories).
- A new isolated prefix restored pynwave2d from the included full Git bundle,
  applied the recorded repair, created a new Python 3.12 venv, and installed all
  exact dependencies from PyPI. `pip check`, imports, and all four scientific
  boundary regression tests passed.
- A second full Python setup invocation on the same prefix passed, reusing the
  pinned checkout/venv. No duplicated patch or unwanted branch movement.
- `git bundle verify` passed for the complete pynwave history bundle. It contains
  the original branches and the three newly archived work snapshots.
- A separate clean Dendro prefix successfully extracted the checksum-verified
  Debian packages, linked the compatible preinstalled MPI runtime, and configured
  CMake with all five sources pinned and FetchContent network access disabled.

In progress at this checkpoint:

- Full tpid and bssnSolver compilation/linkage in that second isolated Dendro
  prefix. Sources and Debian archives were supplied from verified local caches;
  the test does not cover fresh GitHub/apt downloads. The first configure caught
  missing MPI runtime link handling; the recipe was repaired before the passing
  clean configure. This file will be updated when the build finishes.

Separately verified original restoration:

- Dendro tpid and bssnSolver built successfully with these source pins.
- A bounded 12-cubed TwoPunctures solve and one-step BSSN smoke run passed,
  including finite TPID serialization and all 24 evolved checkpoint fields.
  The exact test recipe and original numeric output are included under
  examples/dendro-smoke/. These results precede the second kit rebuild.

Not claimed:

- Fresh remote Git/apt acquisition has not been retested through this kit.
  The original restoration acquired those sources/packages successfully.
- System-wide --deps apt installation, other distributions, macOS, Windows,
  alternate Python versions, and different CPU architectures are untested.
- Python wheels are version-pinned, not hash-locked or vendored. Debian live
  mirrors and public GitHub availability remain external dependencies.
- No convergence, long-evolution validity, or restoration of old simulation
  output/checkpoints is implied by these installation tests.
