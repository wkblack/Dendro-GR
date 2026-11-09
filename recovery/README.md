# Research-computer recovery kit

Prepared 2026-11-09. Restore into a fresh directory after a cloud-computer wipe.
Use the whole ZIP or the `recovery/` directory from the GitHub backup. Keep all
neighboring files with `setup.sh`; only the ZIP includes the full Git history
bundle. A text-only copy uses the exact verified remote source-tree fallback.
It rebuilds tools, not deleted simulation checkpoints or historical output data.

## Quick start

Unzip this archive, open a terminal in its folder, and inspect the plan:

```bash
bash setup.sh --plan --prefix "$HOME/research-recovery"
```

On the matching Debian 13 x86_64 cloud base (GCC 14, OpenMPI 5.0.7 and
BLAS/LAPACK runtimes already present), no administrator privileges are needed:

```bash
bash setup.sh --deps local-apt --prefix "$HOME/research-recovery" --jobs 4
source "$HOME/research-recovery/activate.sh"
```

On a fresh Debian/Ubuntu machine with administrator access:

```bash
bash setup.sh --deps apt --prefix "$HOME/research-recovery" --jobs 4
source "$HOME/research-recovery/activate.sh"
```

`--deps apt` explicitly runs apt-get update and installs OS packages with sudo.
It uses the distribution's current packages, not an immutable OS image. Python
3.12 or newer must already be available; select it with `--python /path/to/python`.
GCC/G++, gfortran, CMake 3.x, MPI, GSL, BLAS/LAPACK, Git, and Python venv support
are required. `--deps existing` (the default) does not install OS packages and
works with manually provisioned prerequisites. Linux is tested. macOS and
Windows builds are not claimed; use a Debian container/VM for this exact recipe.

For Python only, or sources only:

```bash
bash setup.sh --only pynwave --prefix "$HOME/pynwave-recovery"
bash setup.sh --checkout-only --prefix "$HOME/research-sources"
```

No username, password, token, SSH key, API key, or browser session is needed for
the included source bundle and public repositories. Authenticate separately only
if you later choose to push changes. This kit never pushes or creates accounts.

## What is recovered

- Dendro-GR, David Van Komen's experimental branch at
  `d00a675aa6a379d91a5ab0329a2088420d7d19dd`, with `tpid` and `bssnSolver` targets.
  TwoPunctures is bundled in `BSSN_GR`; it is not a separate repository here.
- Dendro-5.01 at `0e6198bf4cae3307a59b4c4a0037ee44979fec2f`.
- toml11, spdlog, and libxsmm at the full commits in `manifest.json`. In
  particular, libxsmm is frozen rather than silently following its `main` tip.
- pynwave2d's surviving `fix/bssn-boundary-parity-ghost-constraints` state at
  `918dcfb30574a4d5fd52ae51d460078d47393e00`, plus the exact `typing.Any` import
  repair in `patches/`. This is the historical research branch, not a merge with
  newer upstream or integration experiments.
- All committed pynwave local branches and full reachable history in the
  verified `bundles/pynwave2d.bundle`, including three preservation snapshots:
  active runtime repair, unfinished spherical-background work, and old runtime
  test evidence. Their local refs and commit/tree provenance are recorded in
  `pynwave-local-snapshots.json`. Only the active branch is built automatically.
- An isolated Python virtual environment with exact captured package versions;
  the source is registered with a `.pth` file so `import nwave` works anywhere.
- Local activation settings for headless plotting, writable matplotlib/Numba
  caches, deterministic one-thread defaults, tool paths, and (when needed)
  the local compiler/library prefix. Existing user thread settings remain
  respected when sourcing activation; setup's own tests use one thread.

All source checkouts use detached HEAD at a full recorded commit. Branch names
in the manifest are provenance, not permission to advance a branch. To develop,
create a new branch explicitly. The original local branches are not changed.

## Preserving the other experimental branches

The included source backup is a complete Git bundle, not a source tarball. For a separate
writable checkout containing the branch history:

```bash
git clone bundles/pynwave2d.bundle recovered-pynwave-history
cd recovered-pynwave-history
git branch -a
# Example: inspect the archived active runtime repair on a NEW local branch:
git switch -c inspect-runtime origin/backup/beta-cloud-20261109/cloud-restoration
```

The active runtime snapshot's original local commit is
`8ff118c0bfd8b16adbdad89dfa9f1becb96cd3bb`. The spherical WIP and runtime-evidence
snapshots are not promoted to production or silently merged. If corresponding
GitHub backup commits were reconstructed with different metadata, their commit
IDs may differ while tree content agrees; the bundle preserves original IDs.

For future backups, `snapshot.sh` creates a new verified local Git bundle and
ref/status inventory without changing the repository:

```bash
bash snapshot.sh /path/to/repository /new/durable-backup-directory
```

Review/commit selected research files to a separate branch before snapshotting.
This helper does not include uncommitted changes or untracked files, and does
not upload anything. Copy the resulting bundle to durable storage. Keep large
outputs/checkpoints in a separate data archive, and update `manifest.json` pins
only when intentionally adopting and testing a new source state.

## Safety and reruns

- Choose a new empty prefix. A nonempty unrelated directory is refused.
- Never resets, cleans, rebases, or checks out over an existing changed source.
- A previously managed prefix can be rerun at the same pins/settings. Source
  modifications beyond the recorded repair are refused and preserved.
- A manually edited activation file is preserved, with an actionable error.
- Changes to build options require another prefix rather than destroying the
  old build. Interrupted clones remain as `.incomplete` directories for review.
- No edits to home dotfiles, global Git settings, or OS preferences. No secrets
  are copied. Activation is opt-in with `source`; no startup file is changed.
- Builds use four jobs by default. Reduce `--jobs` for memory-constrained hosts.
  CPU architecture defaults to `native`; rebuild rather than transferring
  compiled binaries to a different CPU. This is not bit-for-bit reproducibility.
- Python package versions are pinned but wheel hashes are not. Registry access
  is required. Dendro's public repositories require GitHub access; only pynwave
  source is bundled. A pin/download failure stops recovery rather than silently
  switching versions. Signed Debian package metadata and recorded archive
  SHA256s are both checked in `local-apt` mode. If those exact Debian versions
  leave the live mirror, use a compatible manually provisioned environment or
  intentionally update/retest the lock, not an unchecked substitution.
- The rootless Debian mode is intentionally restricted to its recorded base;
  it is not a generic cross-distro package manager. It extracts packages locally
  and links required libraries from the already-installed compatible runtime.

## Verification

Every setup run writes its commands and a machine-readable result into the
prefix's `logs/` directory. Defaults include Python imports, `pip check`, the four
boundary regression tests, successful `tpid`/`bssnSolver` builds, and on Linux a
check for unresolved dynamic libraries. `--no-verify` skips regression/import/
linkage checks, not compilation or `pip check`.

For a bounded actual TwoPunctures solve and one BSSN step on Linux:

```bash
source "$HOME/research-recovery/activate.sh"
bash examples/dendro-smoke/run-smoke.sh "$RESEARCH_ROOT/build/dendro" /tmp
```

This creates a NEW output directory, caps TPID at 120 seconds and BSSN at 300
seconds, and validates finite values. Allow roughly 7 GiB virtual memory and
at least 200 MB output storage. The original restoration passed with TPID
12x12x12 residual `9.163643e-13`; BSSN reached step 1 at time
`0.0651041666667`, with all 24 fields finite across 702,157 checkpoint nodes.
The original result is retained in `examples/dendro-smoke/validation.json`.
This is an installation smoke test, not an accuracy or convergence claim.

Python evolution examples are in `examples/pynwave-*.toml`. Copy each to a new
run directory before running `python "$RESEARCH_ROOT/src/pynwave2d/bssn/solver.py"
<parameter-file>` so relative output stays isolated. The original E642 400-step
and masked JT4 40-step smoke runs had finite saved output. The source still emits
its known invalid-square-root horizon diagnostic warning; it has not been
silenced or interpreted as proof of a physically valid long evolution.

See `VALIDATION.md` for exactly what was tested for this recovery kit.

## Verified secondary recovery remote

If the Git bundle is absent (for example a text-only GitHub copy of this kit),
setup uses `wkblack/pynwave2d` branch
`backup/beta-cloud-20261109/cloud-restoration`, pinned at
`c9e938333cce018e2a651455a5944a581fdd2220`. It verifies source tree
`755f0962b72c32650acc117008ba69b9b97f43cf`, exactly matching the original repaired
local snapshot. No additional patch is applied to this fallback. The full ZIP
is preferable because it also preserves the original history and other branches.

Verified source: https://github.com/wkblack/pynwave2d/tree/backup/beta-cloud-20261109/cloud-restoration
