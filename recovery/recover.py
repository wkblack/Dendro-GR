#!/usr/bin/env python3
"""Conservative, pinned recovery into a dedicated prefix. Standard library only."""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / 'manifest.json').read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def fail(message):
    raise RuntimeError(message)


def clean_env():
    env = dict(os.environ)
    # Do not inherit a parent checkout's Git identity or virtual environment.
    for k in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        env.pop(k, None)
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', NUMBA_NUM_THREADS='1', MPLBACKEND='Agg')
    return env


class Recovery:
    def __init__(self, args):
        self.a = args
        self.root = Path(args.prefix).expanduser().resolve()
        self.env = clean_env()
        self.env['MPLCONFIGDIR'] = str(self.root / 'cache/matplotlib')
        self.env['NUMBA_CACHE_DIR'] = str(self.root / 'cache/numba')
        self.log = None
        self.state = {'schema': 1, 'managed_files': {}}
        self.results = []

    def run(self, args, cwd=None, env=None, capture=False):
        args = [str(x) for x in args]
        print('+ ' + shlex.join(args), flush=True)
        p = subprocess.run(args, cwd=cwd, env=env or self.env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if self.log:
            self.log.write('+ ' + shlex.join(args) + '\n' + p.stdout + '\n')
            self.log.flush()
        if not capture or p.returncode:
            print(p.stdout, end='', flush=True)
        if p.returncode:
            fail(f'Command exited {p.returncode}: {shlex.join(args)}. See the run log; no cleanup or reset performed.')
        return p.stdout.strip()

    def git(self, dest, *args):
        return self.run(['git', '-C', dest, *args], capture=True)

    def managed_write(self, path, text):
        path = Path(path)
        if path.is_symlink():
            fail(f'Refusing to replace symlink: {path}')
        relative = str(path.relative_to(self.root))
        data = text.encode()
        expected = self.state['managed_files'].get(relative)
        if path.exists() and path.read_bytes() != data and (not expected or sha(path) != expected):
            fail(f'User-modified file preserved: {path}. Move it aside explicitly before rerunning.')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.state['managed_files'][relative] = hashlib.sha256(data).hexdigest()
        self.save_state()

    def save_state(self):
        target = self.root / '.recovery-state.json'
        tmp = self.root / '.recovery-state.tmp'
        tmp.write_text(json.dumps(self.state, indent=2) + '\n')
        os.replace(tmp, target)

    @contextlib.contextmanager
    def workspace(self):
        marker = self.root / '.recovery-state.json'
        if self.root.exists() and not marker.exists() and any(self.root.iterdir()):
            fail(f'Prefix is nonempty and not managed by this recovery kit: {self.root}. Choose a new prefix.')
        self.root.mkdir(parents=True, exist_ok=True)
        lock = (self.root / '.recovery.lock').open('a')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail('Another recovery run owns this prefix. Wait for it to finish.')
        if marker.exists():
            self.state = json.loads(marker.read_text())
            if self.state.get('schema') != 1:
                fail('Unrecognized prefix state schema; choose a new prefix.')
        self.save_state()
        for name in ('matplotlib', 'numba', 'pip'):
            (self.root / 'cache' / name).mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        (self.root / 'logs').mkdir(exist_ok=True)
        self.log = (self.root / 'logs' / f'setup-{stamp}.log').open('w')
        try:
            yield
        finally:
            self.log.close()
            lock.close()

    def prerequisites(self):
        for cmd in (self.a.python,):
            if not shutil.which(cmd):
                fail(f'Missing prerequisite {cmd}; install it from your OS vendor first.')
        if self.a.deps == 'apt':
            if platform.system() != 'Linux' or not shutil.which('apt-get'):
                fail('--deps apt requires Debian/Ubuntu apt-get. Other systems: install prerequisites and use --deps existing.')
            sudo = [] if os.geteuid() == 0 else ['sudo']
            if sudo and not shutil.which('sudo'):
                fail('No sudo. Use --deps local-apt on its supported cloud base, or ask an administrator to install prerequisites.')
            self.run(sudo + ['apt-get', 'update'])
            packages = ['build-essential', 'gfortran', 'cmake', 'git', 'pkg-config', 'libgsl-dev',
                        'libopenmpi-dev', 'openmpi-bin', 'libblas-dev', 'liblapack-dev',
                        'python3', 'python3-venv', 'python3-pip', 'ca-certificates']
            self.run(sudo + ['apt-get', 'install', '-y', '--no-install-recommends', *packages])
        elif self.a.deps == 'local-apt':
            self.local_apt()
        if not shutil.which('git', path=self.env['PATH']):
            fail('Missing Git prerequisite. Install it from your OS vendor or use --deps apt.')

    def local_apt(self):
        release = Path('/etc/os-release').read_text() if Path('/etc/os-release').exists() else ''
        if not re.search(r'^ID=debian$', release, re.M) or not re.search(r'^VERSION_ID="?13"?$', release, re.M) or platform.machine() != 'x86_64':
            fail('--deps local-apt is pinned to Debian 13 x86_64 only; use --deps apt or existing elsewhere.')
        for cmd in ('apt-get', 'dpkg-deb', 'gcc', 'g++', 'mpicc', 'mpirun'):
            if not shutil.which(cmd):
                fail(f'local-apt requires base tool {cmd}; this is not the supported cloud base. Use --deps apt.')
        if self.run(['gcc', '-dumpversion'], capture=True).split('.')[0] != '14':
            fail('local-apt requires GCC 14 already installed to match the extracted gfortran 14.')
        mpi = self.run(['mpirun', '--version'], capture=True)
        if not re.search(r'\b5\.0\.7\b', mpi):
            fail('local-apt requires OpenMPI 5.0.7 runtime already installed. Use --deps apt for a complete new base.')
        deps = self.root / 'deps'
        for p in ('lists/partial', 'cache/archives/partial', 'packages', 'root', 'bin'):
            (deps / p).mkdir(parents=True, exist_ok=True)
        keyring = Path('/usr/share/keyrings/debian-archive-keyring.gpg')
        if not keyring.is_file():
            fail('Debian archive signing keyring missing. Refusing unsigned downloads.')
        self.managed_write(deps / 'sources.list', f'deb [signed-by={keyring}] https://deb.debian.org/debian trixie main\n')
        opts = ['-o', f'Dir::Etc::sourcelist={deps}/sources.list', '-o', 'Dir::Etc::sourceparts=-',
                '-o', f'Dir::State::lists={deps}/lists', '-o', f'Dir::Cache={deps}/cache',
                '-o', 'APT::Get::List-Cleanup=0']
        expected = {}
        for line in (HERE / 'debian-packages.sha256').read_text().splitlines():
            digest, name = line.split()
            expected[name] = digest
        missing = any(not (deps / 'packages' / name).exists() for name in expected)
        if missing:
            self.run(['apt-get', *opts, 'update'])
            packages = [line.replace('\t', '=') for line in (HERE / 'debian-packages.lock').read_text().splitlines() if line]
            self.run(['apt-get', *opts, 'download', *packages], cwd=deps / 'packages')
        for name, digest in expected.items():
            path = deps / 'packages' / name
            if not path.is_file() or sha(path) != digest:
                fail(f'Package missing or checksum mismatch: {name}. No unverified archive will be extracted.')
            self.run(['dpkg-deb', '-x', path, deps / 'root'])
        # Debian -dev archives contain linker symlinks to runtime packages already
        # installed on this cloud base. Anchor only those known libraries locally.
        libdir = deps / 'root/usr/lib/x86_64-linux-gnu'
        runtimes = ['libmpi.so.40', 'libmpi_java.so.40', 'libmpi_mpifh.so.40',
                    'libmpi_usempif08.so.40', 'libmpi_usempi_ignore_tkr.so.40',
                    'libmpi_mpifh-gfortran.so.40', 'libmpi_usempif08-gfortran.so.40',
                    'libmpi_usempi_ignore_tkr-gfortran.so.40', 'libopen-pal.so.80',
                    'liboshmem.so.40', 'libprrte.so.3']
        for name in runtimes:
            target = Path('/usr/lib/x86_64-linux-gnu') / name
            local = libdir / name
            if not target.exists():
                fail(f'Missing required base runtime library {target}; use --deps apt.')
            if local.is_symlink():
                if local.readlink() != target:
                    fail(f'Unexpected local library link preserved: {local}')
            elif local.exists():
                fail(f'Unexpected local library file preserved: {local}')
            else:
                local.symlink_to(target)
        wrapper = '#!/bin/sh\nROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"\nexec "$ROOT/deps/root/usr/bin/x86_64-linux-gnu-gfortran-14" -B"$ROOT/deps/root/usr/lib/gcc/x86_64-linux-gnu/14/" -B/usr/lib/gcc/x86_64-linux-gnu/14/ -B/usr/libexec/gcc/x86_64-linux-gnu/14/ "$@"\n'
        self.managed_write(deps / 'bin/gfortran', wrapper)
        (deps / 'bin/gfortran').chmod(0o755)
        self.env['PATH'] = f'{deps}/bin:{deps}/root/usr/bin:' + self.env['PATH']
        for key, value in self.local_env().items():
            self.env[key] = value + (':' + self.env[key] if self.env.get(key) and key in ('LD_LIBRARY_PATH', 'COMPILER_PATH') else '')

    def local_env(self):
        deps = self.root / 'deps'
        return {
            'LD_LIBRARY_PATH': f'{deps}/root/usr/lib/x86_64-linux-gnu',
            'COMPILER_PATH': f'{deps}/root/usr/lib/gcc/x86_64-linux-gnu/14:/usr/lib/gcc/x86_64-linux-gnu/14:/usr/libexec/gcc/x86_64-linux-gnu/14',
            'OMPI_CPPFLAGS': f'-I{deps}/root/usr/lib/x86_64-linux-gnu/openmpi/include -I{deps}/root/usr/lib/x86_64-linux-gnu/openmpi/include/openmpi',
            'OMPI_FCFLAGS': f'-I{deps}/root/usr/lib/x86_64-linux-gnu/fortran/gfortran-mod-15/openmpi -I{deps}/root/usr/lib/x86_64-linux-gnu/openmpi/include',
            'OMPI_LDFLAGS': f'-L{deps}/root/usr/lib/x86_64-linux-gnu/openmpi/lib',
            'OMPI_FC': f'{deps}/bin/gfortran',
        }

    def checkout(self, repo):
        # A text-only copy can recover the exact repaired tree from the verified
        # backup remote. The full archive instead retains original local history.
        if repo.get('bundle') and not (HERE / repo['bundle']).is_file():
            if not repo.get('fallback'):
                fail(f'Missing required source bundle: {repo["bundle"]}')
            repo = dict(repo, **repo['fallback'])
            repo.pop('patch', None)
            repo.pop('bundle', None)
        dest = self.root / 'src' / repo['name']
        if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?', repo['url']):
            fail('Manifest URL must be a public credential-free GitHub HTTPS URL.')
        if not re.fullmatch('[0-9a-f]{40}', repo['commit']):
            fail('Manifest must contain full SHA-1 commit pins.')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            temp = dest.with_name(dest.name + '.incomplete')
            if temp.exists():
                fail(f'Partial prior clone preserved at {temp}; inspect it and choose a new prefix or move it aside.')
            bundle = HERE / repo['bundle'] if repo.get('bundle') else None
            if bundle and bundle.is_file():
                self.run(['git', 'clone', '--no-checkout', bundle, temp])
                self.git(temp, 'remote', 'set-url', 'origin', repo['url'])
            else:
                self.run(['git', 'clone', '--no-checkout', '--filter=blob:none', repo['url'], temp])
            # Full pin, never branch tip. Fail closed if the recorded commit cannot be obtained.
            if subprocess.run(['git', '-C', str(temp), 'cat-file', '-e', repo['commit'] + '^{commit}'], env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                self.git(temp, 'fetch', 'origin', repo['commit'])
            self.git(temp, 'checkout', '--detach', repo['commit'])
            os.rename(temp, dest)
        else:
            if not (dest / '.git').is_dir() or self.git(dest, 'rev-parse', 'HEAD') != repo['commit']:
                fail(f'Existing source is not the pinned managed checkout: {dest}. It was not changed.')
            if self.git(dest, 'remote', 'get-url', 'origin') != repo['url']:
                fail(f'Existing checkout origin changed: {dest}. It was not changed.')
        if repo.get('tree') and self.git(dest, 'rev-parse', 'HEAD^{tree}') != repo['tree']:
            fail(f'Recovery snapshot tree mismatch: {dest}')
        diff = self.run(['git', '-C', dest, 'diff', '--binary', 'HEAD'], capture=True)
        patch = HERE / repo['patch'] if repo.get('patch') else None
        if patch:
            expected = patch.read_text().strip()
            if diff and diff != expected:
                fail(f'Unexpected local modifications preserved: {dest}')
            if not diff:
                self.git(dest, 'apply', '--check', str(patch))
                self.git(dest, 'apply', str(patch))
        elif diff:
            fail(f'Local tracked modifications preserved: {dest}')
        self.results.append({'repository': repo['name'], 'commit': repo['commit'], 'branch_provenance': repo['branch'], 'checked_out': 'detached HEAD', 'patch': repo.get('patch')})

    def python(self):
        version = self.run([self.a.python, '-c', 'import sys;print("%d.%d" % sys.version_info[:2])'], capture=True)
        if tuple(map(int, version.split('.'))) < (3, 12):
            fail('Python >=3.12 required for the captured dependency lock. Choose --python /path/to/python3.12.')
        venv = self.root / 'venv'
        if not venv.exists():
            self.run([self.a.python, '-m', 'venv', venv])
        py = venv / 'bin/python'
        self.run([py, '-m', 'pip', '--isolated', '--disable-pip-version-check', '--cache-dir', self.root / 'cache/pip', 'install', '--index-url', 'https://pypi.org/simple', '-r', HERE / MANIFEST['python']['lock']])
        source = self.root / 'src/pynwave2d'
        site = Path(self.run([py, '-c', 'import site;print(site.getsitepackages()[0])'], capture=True))
        if not site.resolve().is_relative_to(venv.resolve()):
            fail('Unexpected venv site-packages outside managed prefix.')
        self.managed_write(site / 'pynwave2d-source.pth', str(source) + '\n')
        self.run([py, '-m', 'pip', '--isolated', '--disable-pip-version-check', '--cache-dir', self.root / 'cache/pip', 'check'])
        if not self.a.no_verify:
            self.run([py, '-c', 'import nwave,numpy,scipy,numba,pentapy,h5py,matplotlib,pandas,seaborn,plotly;print("Python imports passed")'])
            self.run([py, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_bssn_boundaries.py', '-v'], cwd=source)
            self.results.append({'verification': 'pynwave imports, pip check, four boundary regressions', 'status': 'passed'})

    def dendro(self):
        for cmd in ('cmake', 'gcc', 'g++', 'gfortran', 'mpicc', 'mpicxx', 'mpirun', 'make'):
            if not shutil.which(cmd, path=self.env['PATH']):
                fail(f'Missing build prerequisite {cmd}; use --deps apt or supported --deps local-apt.')
        source = self.root / 'src/Dendro-GR'
        build = self.root / 'build/dendro'
        opts = list(MANIFEST['build']['cmake_options'])
        opts += [f'-DCPU_ARCH={self.a.cpu_arch}', f'-DDENDRO_dendrolib_DIR={self.root}/src/Dendro-5.01',
                 f'-DFETCHCONTENT_SOURCE_DIR_TOML11={self.root}/src/toml11',
                 f'-DFETCHCONTENT_SOURCE_DIR_SPDLOG={self.root}/src/spdlog',
                 f'-DFETCHCONTENT_SOURCE_DIR_XSMM={self.root}/src/libxsmm',
                 '-DFETCHCONTENT_FULLY_DISCONNECTED=ON']
        if self.a.deps == 'local-apt':
            opts += [f'-DCMAKE_Fortran_COMPILER={self.root}/deps/bin/gfortran',
                     f'-DCMAKE_PREFIX_PATH={self.root}/deps/root/usr',
                     f'-DGSL_ROOT_DIR={self.root}/deps/root/usr',
                     '-DBLAS_LIBRARIES=/usr/lib/x86_64-linux-gnu/libblas.so.3',
                     '-DLAPACK_LIBRARIES=/usr/lib/x86_64-linux-gnu/liblapack.so.3']
            for name in ('mpi', 'mpi_mpifh', 'mpi_usempif08', 'mpi_usempi_ignore_tkr'):
                opts.append(f'-DMPI_{name}_LIBRARY=/usr/lib/x86_64-linux-gnu/lib{name}.so.40')
        config_key = hashlib.sha256(json.dumps(opts).encode()).hexdigest()
        old = self.state.get('dendro_configuration')
        if old and old != config_key:
            fail('Build options changed for an existing prefix. Use a separate prefix to preserve the old build.')
        self.state['dendro_configuration'] = config_key
        self.save_state()
        env = dict(self.env, GIT_DIR=str(source / '.git'), GIT_WORK_TREE=str(source))
        self.run(['cmake', '-S', source, '-B', build, *opts], env=env)
        self.run(['cmake', '--build', build, '--target', *MANIFEST['build']['targets'], '--parallel', self.a.jobs], env=env)
        for target in MANIFEST['build']['targets']:
            binary = build / 'BSSN_GR' / target
            if not binary.is_file() or not os.access(binary, os.X_OK):
                fail(f'Build reported success but executable is missing: {binary}')
            if not self.a.no_verify and platform.system() == 'Linux':
                linked = self.run(['ldd', binary], capture=True)
                if 'not found' in linked:
                    fail(f'Unresolved runtime library for {binary}:\n{linked}')
        self.results.append({'verification': 'tpid and bssnSolver build and dynamic linkage', 'status': 'passed' if not self.a.no_verify else 'build passed; linkage skipped'})

    def activate(self):
        root = shlex.quote(str(self.root))
        content = '# Source this file from bash. Does not edit ~/.bashrc or global preferences.\n'
        content += f'export RESEARCH_ROOT={root}\n'
        if self.a.deps == 'local-apt':
            content += 'export PATH="$RESEARCH_ROOT/deps/bin:$RESEARCH_ROOT/deps/root/usr/bin:$PATH"\n'
            for key, value in self.local_env().items():
                content += 'export ' + key + '=' + shlex.quote(value)
                if key in ('LD_LIBRARY_PATH', 'COMPILER_PATH'):
                    content += '"${' + key + ':+:$' + key + '}"'
                content += '\n'
        content += 'export PATH="$RESEARCH_ROOT/build/dendro/BSSN_GR:$PATH"\n'
        content += 'if [ -f "$RESEARCH_ROOT/venv/bin/activate" ]; then . "$RESEARCH_ROOT/venv/bin/activate"; fi\n'
        content += 'export MPLCONFIGDIR="$RESEARCH_ROOT/cache/matplotlib"\nexport NUMBA_CACHE_DIR="$RESEARCH_ROOT/cache/numba"\n'
        content += 'export MPLBACKEND="${MPLBACKEND:-Agg}"\n'
        content += 'export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"\nexport OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"\nexport NUMBA_NUM_THREADS="${NUMBA_NUM_THREADS:-1}"\n'
        self.managed_write(self.root / 'activate.sh', content)

    def execute(self):
        selected = [r for r in MANIFEST['repositories'] if self.a.only in ('all', r['group'])]
        if self.a.plan:
            print(json.dumps({'prefix': str(self.root), 'deps': self.a.deps, 'jobs': self.a.jobs, 'repositories': selected, 'checkout_only': self.a.checkout_only, 'verify': not self.a.no_verify, 'cmake': MANIFEST['build']}, indent=2))
            print('Plan only: no files, installs, network, or source modifications performed.')
            return
        with self.workspace():
            self.prerequisites()
            for repo in selected:
                self.checkout(repo)
            if not self.a.checkout_only:
                if self.a.only in ('all', 'pynwave'):
                    self.python()
                if self.a.only in ('all', 'dendro'):
                    self.dendro()
            self.activate()
            report = {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'manifest_sha256': sha(HERE / 'manifest.json'), 'platform': platform.platform(), 'deps_mode': self.a.deps, 'checkout_only': self.a.checkout_only, 'results': self.results, 'scope': 'Installation verification only, not numerical convergence or recovery of old output data.'}
            filename = 'verification-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '.json'
            (self.root / 'logs' / filename).write_text(json.dumps(report, indent=2) + '\n')
            print(f'\nRecovery completed. Activate explicitly: source {shlex.quote(str(self.root / "activate.sh"))}')
            print(f'Verification report: {self.root / "logs" / filename}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefix', default='~/research-recovery', help='Dedicated empty or kit-managed directory')
    p.add_argument('--deps', choices=['existing', 'apt', 'local-apt'], default='existing', help='existing: no dependency OS install; apt: explicit system package install; local-apt: pinned Debian13 amd64 user-space dependencies')
    p.add_argument('--only', choices=['all', 'dendro', 'pynwave'], default='all')
    p.add_argument('--python', default='python3', help='Python >=3.12 executable for the science venv')
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--cpu-arch', default='native', choices=['native','znver1','znver2','znver3','znver4','haswell','broadwell','skylake-avx512','cascadelake','icelake-server','sapphirerapids','generic_avx2','x86-64-v3'])
    p.add_argument('--plan', action='store_true', help='Show exact plan without modifying anything')
    p.add_argument('--checkout-only', action='store_true', help='Recover pinned sources only; no compilation or Python install')
    p.add_argument('--no-verify', action='store_true', help='Skip regression/import/linkage checks, not compilation or pip check')
    a = p.parse_args()
    if a.jobs < 1 or a.jobs > 128:
        p.error('--jobs must be between 1 and 128')
    try:
        Recovery(a).execute()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'RECOVERY STOPPED: {exc}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
