#!/usr/bin/env bash
# Explicit local branch backup. No uploads, no credentials/config, no untracked files.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  printf 'Usage: bash snapshot.sh /path/to/repository /new/backup/directory\n' >&2
  exit 2
fi
repo="$(cd -- "$1" && pwd)"
out="$2"
if [ -e "$out" ]; then
  echo 'Refusing an existing backup destination. Choose a new directory.' >&2
  exit 1
fi
# Review code for secrets before making or sharing a source archive.
git -C "$repo" rev-parse --git-dir >/dev/null
mkdir -p -- "$out"
out="$(cd -- "$out" && pwd)"
git -C "$repo" bundle create "$out/repository.bundle" --all
git -C "$repo" bundle verify "$out/repository.bundle" >"$out/bundle-verification.txt" 2>&1
git -C "$repo" show-ref >"$out/refs.txt"
git -C "$repo" rev-parse HEAD >"$out/HEAD.txt"
git -C "$repo" status --short >"$out/working-tree-status.txt"
printf '%s\n' 'Backup contains committed Git history and refs only.' 'Uncommitted and untracked content is listed, not copied.' 'Review it, commit selected research files to a dedicated branch, then make a new snapshot.' 'No Git configuration, credentials, environment variables, or home dotfiles were copied.' >"$out/README.txt"
printf 'Verified local Git backup: %s\nCopy it to durable storage before a wipe. No upload was performed.\n' "$out"
