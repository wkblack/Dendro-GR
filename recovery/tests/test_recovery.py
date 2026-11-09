"""Offline safety tests using disposable local Git repositories, not research sources."""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

KIT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery', KIT / 'recover.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.old_here = m.HERE
        m.HERE = self.base
        self.args = argparse.Namespace(prefix=str(self.base/'output'), deps='existing', only='pynwave', python='python3', jobs=1, cpu_arch='native', plan=False, checkout_only=True, no_verify=False)
        self.r = m.Recovery(self.args)
    def tearDown(self):
        m.HERE = self.old_here
        self.tmp.cleanup()
    def git(self, *args):
        return subprocess.check_output(['git', *map(str,args)], stderr=subprocess.DEVNULL, text=True).strip()
    def fixture(self):
        src = self.base/'fixture'
        src.mkdir()
        self.git('init', '-b', 'research', src)
        (src/'example.py').write_text('value = 1\n')
        self.git('-C',src,'add','example.py')
        self.git('-C',src,'-c','user.name=Recovery fixture','-c','user.email=fixture@example.invalid','commit','-m','fixture')
        commit=self.git('-C',src,'rev-parse','HEAD')
        self.git('-C',src,'bundle','create',self.base/'fixture.bundle','--all')
        return {'name':'fixture','url':'https://github.com/example/fixture.git','branch':'research','commit':commit,'bundle':'fixture.bundle'}
    def test_nonempty_unmanaged_prefix_is_not_changed(self):
        self.r.root.mkdir()
        sentinel=self.r.root/'important.txt'; sentinel.write_text('keep me')
        with self.assertRaisesRegex(RuntimeError,'nonempty'):
            with self.r.workspace(): pass
        self.assertEqual(sentinel.read_text(),'keep me')
        self.assertEqual(list(self.r.root.iterdir()),[sentinel])
    def test_checkout_is_repeatable_and_keeps_bundle_branches(self):
        repo=self.fixture()
        with self.r.workspace():
            self.r.checkout(repo); self.r.checkout(repo)
            dest=self.r.root/'src/fixture'
            self.assertEqual(self.git('-C',dest,'rev-parse','HEAD'),repo['commit'])
            self.assertIn('origin/research',self.git('-C',dest,'branch','-a'))
            self.assertEqual(self.git('-C',dest,'rev-parse','--abbrev-ref','HEAD'),'HEAD')
    def test_dirty_source_refused_without_overwrite(self):
        repo=self.fixture()
        with self.r.workspace():
            self.r.checkout(repo)
            target=self.r.root/'src/fixture/example.py'
            target.write_text('user change\n')
            with self.assertRaisesRegex(RuntimeError,'modifications preserved'):
                self.r.checkout(repo)
            self.assertEqual(target.read_text(),'user change\n')
    def test_managed_settings_edits_preserved(self):
        with self.r.workspace():
            target=self.r.root/'activate.sh'
            self.r.managed_write(target,'one\n')
            self.r.managed_write(target,'two\n')
            target.write_text('my customization\n')
            with self.assertRaisesRegex(RuntimeError,'User-modified'):
                self.r.managed_write(target,'three\n')
            self.assertEqual(target.read_text(),'my customization\n')
    def test_symlink_settings_refused(self):
        with self.r.workspace():
            outside=self.base/'outside'; outside.write_text('keep')
            target=self.r.root/'activate.sh'; target.symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError,'symlink'):
                self.r.managed_write(target,'new')
            self.assertEqual(outside.read_text(),'keep')
    def test_plan_has_no_filesystem_side_effect(self):
        self.args.plan=True
        with contextlib.redirect_stdout(io.StringIO()): self.r.execute()
        self.assertFalse(self.r.root.exists())
    def test_fallback_uses_verified_tree_when_bundle_absent(self):
        repo=self.fixture()
        with self.r.workspace():
            self.r.checkout(repo)
            dest=self.r.root/'src/fixture'
            tree=self.git('-C',dest,'rev-parse','HEAD^{tree}')
            repo['fallback']={'url':repo['url'],'branch':'backup/recovered','commit':repo['commit'],'tree':tree}
            (self.base/'fixture.bundle').unlink()
            self.r.checkout(repo)
            self.assertEqual(self.r.results[-1]['branch_provenance'],'backup/recovered')
    def test_fallback_rejects_wrong_tree(self):
        repo=self.fixture()
        with self.r.workspace():
            self.r.checkout(repo)
            repo['fallback']={'url':repo['url'],'branch':'backup/recovered','commit':repo['commit'],'tree':'0'*40}
            (self.base/'fixture.bundle').unlink()
            with self.assertRaisesRegex(RuntimeError,'tree mismatch'):
                self.r.checkout(repo)
    def test_no_secrets_in_manifest_urls(self):
        repo=self.fixture(); repo['url']='https://secret@github.com/example/repo.git'
        with self.r.workspace():
            with self.assertRaisesRegex(RuntimeError,'credential-free'):
                self.r.checkout(repo)

if __name__=='__main__': unittest.main(verbosity=2)
