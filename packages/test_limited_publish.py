import hashlib
import importlib.util
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = Path(__file__).resolve().parent / 'limited_publish.py'
REAL_PACKAGE = '52c07d734d0b597d69e9b9c9b2ccb4042dada345'
REAL_CUTOFF = '2026-11-24T18:05:20.756572+08:00'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lp = load('limited_publish', PUBLISHER)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def git_run(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class RealPackageTests(unittest.TestCase):
    def test_real_frozen_package_is_readable_without_feed_or_writes(self):
        before = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'])
        source = lp.inspect_frozen_source(ROOT, now='2026-11-25T09:00:00+08:00')
        after = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'])
        self.assertEqual(before, after)
        self.assertFalse((ROOT / '2026-11-25.md').exists())
        self.assertEqual(source['source_commit_sha'], REAL_PACKAGE)
        self.assertEqual(source['source_date'], '2026-11-24')
        self.assertEqual(source['source_cutoff'], REAL_CUTOFF)
        self.assertEqual(source['source_package_path'], 'packages/2026-11-24/')
        self.assertEqual(source['clean_incremental_count'], 195)
        self.assertEqual(source['incremental_lines'], 195)
        self.assertGreater(source['source_status_count'], 0)
        self.assertNotEqual(source['source_commit_sha'], git(ROOT, 'rev-parse', 'HEAD'))


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.cutoff = REAL_CUTOFF
        self.source_day = '2026-11-24'
        self.rows = [
            {'record_id': 'R-1', 'source_id': 'official', 'title': '模型发布'},
            {'record_id': 'R-2', 'source_id': 'papers', 'title': '论文收录'},
        ]
        self._init_repo()
        self.body = 'AI Builders Digest — 2026-11-25\n\n发布日：2026-11-25。源批次：2026-11-24 18:05 冻结包。\n'.encode()
        self.now = '2026-11-25T09:00:00+08:00'

    def _init_repo(self, *, cutoff=None, bad_hash=False, latest_status='ready', omit_status=False):
        cutoff = cutoff or self.cutoff
        if self.repo.exists():
            shutil.rmtree(self.repo)
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.repo)], check=True)
        git_run(self.repo, 'config', 'user.name', 'Package Test')
        git_run(self.repo, 'config', 'user.email', 'test@example.invalid')
        (self.repo / '2026-11-23.md').write_text('历史早报 11-23\n', encoding='utf-8')
        (self.repo / '2026-11-24.md').write_text('历史早报 11-24，不能被下一期覆盖。\n', encoding='utf-8')
        git_run(self.repo, 'add', '2026-11-23.md', '2026-11-24.md')
        git_run(self.repo, 'commit', '-m', 'historical digests')
        historical = git(self.repo, 'rev-parse', 'HEAD')
        archived = (self.repo / '2026-11-24.md').read_bytes()
        day = cutoff[0:10]
        package = self.repo / 'packages' / day
        package.mkdir(parents=True)
        incremental = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in self.rows)
        (package / 'incremental.jsonl').write_text(incremental, encoding='utf-8')
        statuses = []
        for row in self.rows:
            item = {
                'source_id': row['source_id'],
                'name': row['source_id'],
                'status': 'partial',
                'package_incremental_count': 1,
                'cutoff': cutoff,
            }
            if omit_status:
                del item['status']
            statuses.append(item)
        (package / 'source_status.json').write_text(json.dumps(statuses, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        pointer = {
            'date': day,
            'status': 'archived',
            'digest_path': '2026-11-24.md',
            'commit_sha': historical,
            'sha256': sha256(archived),
            'relationship': 'existing_same_calendar_date_remix; not generated from this later collection package',
            'digest_cutoff': None,
            'collection_cutoff': cutoff,
        }
        (package / 'digest-pointer.json').write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        files = {}
        for name in ('incremental.jsonl', 'source_status.json', 'digest-pointer.json'):
            data = (package / name).read_bytes()
            files[name] = {'sha256': '0' * 64 if bad_hash and name == 'incremental.jsonl' else sha256(data),
                           'bytes': len(data)}
        manifest = {
            'schema_version': 'clean-daily-package/1',
            'date': day,
            'status': 'ready',
            'cutoff': cutoff,
            'clean_incremental_count': len(self.rows),
            'files': files,
        }
        (package / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        git_run(self.repo, 'add', f'packages/{day}')
        git_run(self.repo, 'commit', '-m', 'frozen package')
        package_commit = git(self.repo, 'rev-parse', 'HEAD')
        dump(self.repo / 'packages' / 'latest.json', {
            'date': day,
            'status': latest_status,
            'commit_sha': package_commit,
            'digest_path': '2026-11-24.md',
            'package_path': f'packages/{day}/',
            'cutoff': cutoff,
        })
        git_run(self.repo, 'add', 'packages/latest.json')
        git_run(self.repo, 'commit', '-m', 'latest pointer')
        git_run(self.repo, 'checkout', '-b', 'feature')
        self.package_commit = package_commit
        self.historical_digest = (self.repo / '2026-11-24.md').read_bytes()

    def publish(self, **kwargs):
        args = {
            'body': self.body,
            'publication_date': '2026-11-25',
            'now': self.now,
        }
        args.update(kwargs)
        return lp.publish_limited(self.repo, **args)

    def test_next_morning_uses_previous_frozen_package_without_forging_collection(self):
        head = git(self.repo, 'rev-parse', 'HEAD')
        body_file = Path(self.tmp.name) / 'final.md'
        body_file.write_bytes(self.body)
        completed = subprocess.run([
            'python3', str(PUBLISHER), '--repo', str(self.repo), '--body', str(body_file),
            '--publication-date', '2026-11-25', '--expected-head', head, '--now', self.now,
        ], check=True, capture_output=True, text=True)
        result = json.loads(completed.stdout)
        self.assertFalse(result['idempotent'])
        self.assertEqual(result['publication_date'], '2026-11-25')
        self.assertEqual(result['source_date'], '2026-11-24')
        self.assertEqual(result['source_cutoff'], self.cutoff)
        self.assertEqual(result['source_commit_sha'], self.package_commit)
        self.assertEqual(result['source_package_path'], 'packages/2026-11-24/')
        self.assertFalse(result['collection_created'])
        self.assertIsNone(result['lag_notice'])
        self.assertFalse(result['lag_over_36h'])
        self.assertLess(result['lag_hours'], 36)
        self.assertEqual(result['coverage']['incremental_lines'], 2)
        self.assertEqual(result['coverage']['clean_incremental_count'], 2)
        self.assertEqual(result['coverage']['source_status_count'], 2)
        self.assertEqual(result['digest_sha256'], sha256(self.body))
        self.assertNotEqual(result['digest_commit'], result['source_commit_sha'])
        self.assertNotEqual(result['source_commit_sha'], git(self.repo, 'rev-parse', 'HEAD'))
        self.assertEqual((self.repo / '2026-11-25.md').read_bytes(), self.body)
        self.assertEqual((self.repo / '2026-11-24.md').read_bytes(), self.historical_digest)
        self.assertFalse((self.repo / 'packages' / '2026-11-25').exists())
        self.assertFalse((ROOT / '2026-11-25.md').exists())
        for name in ('manifest.json', 'incremental.jsonl', 'source_status.json', 'digest-pointer.json'):
            subprocess.check_call(['git', '-C', str(self.repo), 'cat-file', '-e', f'{self.package_commit}:packages/2026-11-24/{name}'])
        names = git(self.repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD~1', 'HEAD')
        self.assertNotIn('packages/2026-11-24/incremental.jsonl', names.splitlines())
        self.assertNotIn('packages/latest.json', names.splitlines())
        pointer = lp._load(self.repo / 'packages' / 'publication-latest.json')
        self.assertEqual(pointer['relationship'], result['relationship'])
        self.assertIn('发布日', pointer['relationship'])
        self.assertIn('不是新采集', pointer['relationship'])

    def test_repeat_is_idempotent_and_keeps_source_commit(self):
        first = self.publish()
        head = git(self.repo, 'rev-parse', 'HEAD')
        second = self.publish(expected_head=head, now='2026-11-25T10:00:00+08:00')
        self.assertTrue(second['idempotent'])
        self.assertEqual(second['source_commit_sha'], first['source_commit_sha'])
        self.assertEqual(second['digest_sha256'], first['digest_sha256'])
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), head)

    def test_refusals_do_not_create_ready_publication(self):
        historical = self.historical_digest
        with self.subTest('future cutoff'):
            future = datetime.fromisoformat(self.now) + timedelta(hours=2)
            self._init_repo(cutoff=future.isoformat())
            with self.assertRaises(ValueError) as caught:
                self.publish()
            self.assertIn('未来截止', str(caught.exception))
        self._init_repo()
        with self.subTest('bad hash'):
            self._init_repo(bad_hash=True)
            with self.assertRaises(ValueError) as caught:
                self.publish()
            self.assertIn('哈希', str(caught.exception))
        self._init_repo()
        with self.subTest('missing status'):
            self._init_repo(omit_status=True)
            with self.assertRaises(ValueError) as caught:
                self.publish()
            self.assertIn('来源状态', str(caught.exception))
        self._init_repo()
        with self.subTest('unready latest'):
            self._init_repo(latest_status='partial')
            with self.assertRaises(ValueError) as caught:
                self.publish()
            self.assertIn('ready', str(caught.exception))
        self._init_repo()
        with self.subTest('historical overwrite'):
            with self.assertRaises(ValueError) as caught:
                self.publish(publication_date='2026-11-24', body='另一份正文\n'.encode(), now='2026-11-25T09:00:00+08:00')
            self.assertIn('晚于冻结源', str(caught.exception))
            self.assertEqual((self.repo / '2026-11-24.md').read_bytes(), historical)
        with self.subTest('older source and different historical body'):
            self.cutoff = '2026-11-23T18:05:00+08:00'
            self.rows = [{'record_id': 'R-1', 'source_id': 'official', 'title': '前一日'}]
            self._init_repo(cutoff=self.cutoff)
            before = (self.repo / '2026-11-24.md').read_bytes()
            with self.assertRaises(ValueError):
                self.publish(publication_date='2026-11-24', body='试图覆盖历史早报\n'.encode(), now='2026-11-24T09:00:00+08:00')
            self.assertEqual((self.repo / '2026-11-24.md').read_bytes(), before)
        self.assertFalse((self.repo / 'packages' / 'publication-latest.json').exists())
        self.assertFalse((ROOT / '2026-11-25.md').exists())
        self.assertFalse((self.repo / '2026-11-25.md').exists())

    def test_date_regression_keeps_newer_publication(self):
        self.publish(publication_date='2026-11-26', now='2026-11-26T09:00:00+08:00',
                     body='AI Builders Digest — 2026-11-26\n\n源批次仍是 11-24。\n'.encode())
        stored = (self.repo / 'packages' / 'publication-latest.json').read_bytes()
        with self.assertRaises(ValueError) as caught:
            self.publish(publication_date='2026-11-25', now='2026-11-26T09:30:00+08:00')
        self.assertIn('退回', str(caught.exception))
        self.assertEqual((self.repo / 'packages' / 'publication-latest.json').read_bytes(), stored)
        self.assertFalse((self.repo / '2026-11-25.md').exists())

    def test_lag_over_36_hours_keeps_notice_and_full_coverage(self):
        source = {
            'source_cutoff': self.cutoff,
            'source_date': '2026-11-24',
            'source_commit_sha': 'abc',
            'source_package_path': 'packages/2026-11-24/',
            'source_manifest_sha256': 'd' * 64,
            'clean_incremental_count': 2,
            'incremental_lines': 2,
            'source_status_count': 2,
        }
        exactly = datetime.fromisoformat(self.cutoff) + timedelta(hours=36)
        self.assertIsNone(lp._record_for(self.repo, exactly.date(), self.body, source, exactly)['lag_notice'])
        late = exactly + timedelta(seconds=1)
        result = self.publish(publication_date='2026-11-26', now=late.isoformat(),
                              body='AI Builders Digest — 2026-11-26\n\n仍使用 11-24 冻结批次全文。\n'.encode())
        self.assertTrue(result['lag_over_36h'])
        self.assertGreater(result['lag_hours'], 36)
        self.assertEqual(result['lag_notice'], lp.LAG_NOTICE)
        self.assertIn('没有因滞后删减', result['lag_notice'])
        self.assertEqual(result['coverage']['incremental_lines'], 2)
        self.assertEqual(result['coverage']['source_status_count'], 2)
        self.assertEqual(result['source_commit_sha'], self.package_commit)
        self.assertFalse((self.repo / 'packages' / '2026-11-26' / 'incremental.jsonl').exists())

    def test_refuses_main_dirty_head_and_lock(self):
        git_run(self.repo, 'checkout', 'main')
        with self.assertRaises(ValueError):
            self.publish()
        git_run(self.repo, 'checkout', '-b', 'other')
        (self.repo / 'notes.txt').write_text('dirty\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.publish()
        (self.repo / 'notes.txt').unlink()
        with self.assertRaises(ValueError):
            self.publish(expected_head='0' * 40)
        lock = lp.lock_path(self.repo)
        lock.write_text(str(os.getpid()))
        self.addCleanup(lock.unlink, missing_ok=True)
        with self.assertRaises(ValueError):
            self.publish()
        self.assertFalse((self.repo / '2026-11-25.md').exists())

    def test_feed_root_is_rejected_and_publisher_does_not_collect(self):
        source = PUBLISHER.read_text(encoding='utf-8')
        self.assertNotIn('pkg.build', source)
        self.assertNotIn('pkg.publish', source)
        completed = subprocess.run([
            'python3', str(PUBLISHER), '--repo', str(self.repo), '--body', str(PUBLISHER),
            '--publication-date', '2026-11-25', '--feed-root', '/tmp/validated-public-feed',
        ], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertIn('feed-root', completed.stderr)
        self.assertIn('四文件', completed.stderr)
        self.assertFalse((self.repo / '2026-11-25.md').exists())
        self.assertFalse((ROOT / '2026-11-25.md').exists())


if __name__ == '__main__':
    unittest.main()
