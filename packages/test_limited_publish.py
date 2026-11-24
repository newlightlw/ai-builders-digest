import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / 'tools' / 'export_daily_package.py'
PUBLISHER = Path(__file__).resolve().parent / 'limited_publish.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pkg = load(EXPORTER, 'export_daily_package')
lp = load(PUBLISHER, 'limited_publish')


class LimitedPublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        (self.repo / 'tools').mkdir(parents=True)
        self.feed = self.root / 'feed'
        self.snap = self.feed / 'snapshot'
        self.snap.mkdir(parents=True)
        policy = {'sources': [{'source_id': 'official', 'decision': 'keep', 'group': '海外厂商与模型'},
                              {'source_id': 'papers', 'decision': 'keep', 'group': '论文与研究'},
                              {'source_id': 'noise', 'decision': 'exclude', 'group': '按需'}],
                  'source_item_cap': 15, 'caps': {}}
        pkg.dump(self.repo / 'tools/source_policy.json', policy)
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.repo)], check=True)
        pkg.git(self.repo, 'config', 'user.name', 'Package Test')
        pkg.git(self.repo, 'config', 'user.email', 'test@example.invalid')
        self.other = self.repo / '2026-11-22.md'
        self.other.write_text('Earlier archive must stay byte-identical.\n', encoding='utf-8')
        self.commit_all('fixture policy')
        self.day = '2026-11-23'
        self.cutoff = '2026-11-23T18:05:00+08:00'
        self.body = 'AI Builders Digest — 2026-11-23\n\n深度分析：模型发布不等于部署完成。\n'.encode()
        self.data = []
        for rid, sid, url in [('R-one', 'official', 'https://arxiv.org/abs/2611.12345v2'),
                              ('R-two', 'papers', 'https://huggingface.co/papers/2611.12345'),
                              ('R-three', 'noise', 'https://example.com/noise')]:
            row = {k: None for k in pkg.DATE_FIELDS}
            row.update(record_id=rid, source_id=sid, source_name=sid, title='Synthetic model research', url=url,
                       fetched_at='2026-11-23T18:10:00+08:00', published_on='2026-11-23',
                       date_role='publication', material_status='abstract_only', effective_kind='paper_metadata',
                       time_bucket='published_today', archive_change='new_to_archive')
            self.data.append(row)
        self.write_feed()
        self.branch('feature')

    def commit_all(self, message):
        pkg.git(self.repo, 'add', '.')
        pkg.git(self.repo, 'commit', '-qm', message)

    def branch(self, name):
        subprocess.run(['git', '-C', str(self.repo), 'checkout', '-q', '-b', name], check=True)

    def write_feed(self):
        text = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in self.data)
        (self.snap / 'catalog.jsonl').write_text(text)
        (self.snap / 'incremental.jsonl').write_text(text)
        pkg.dump(self.snap / 'manifest.json', {'cutoff': self.cutoff, 'record_count': len(self.data),
                 'incremental_count': len(self.data), 'source_count': 3})
        pkg.dump(self.snap / 'export-validation.json', {'status': 'PASS', 'checks': {'synthetic_check': True}})
        pkg.dump(self.snap / 'source_status.json', [{'source_id': sid, 'source_name': sid, 'status': 'partial',
                 'retained_count': 1, 'cutoff': self.cutoff, 'limitations': []}
                 for sid in ['official', 'papers', 'noise']])
        pkg.dump(self.feed / 'latest.json', {'status': 'ready', 'cutoff': self.cutoff, 'snapshot': str(self.snap)})

    def publish(self, **kwargs):
        args = {'body': self.body, 'feed_root': self.feed}
        args.update(kwargs)
        return lp.publish_limited(self.repo, **args)

    def test_cli_publishes_body_package_and_separated_latest(self):
        body = self.root / 'final.md'
        body.write_bytes(self.body)
        head = pkg.git(self.repo, 'rev-parse', 'HEAD')
        completed = subprocess.run([
            'python3', str(PUBLISHER), '--repo', str(self.repo), '--feed-root', str(self.feed),
            '--body', str(body), '--expected-head', head, '--date', self.day,
        ], check=True, capture_output=True, text=True)
        result = json.loads(completed.stdout)
        self.assertFalse(result['idempotent'])
        self.assertEqual(result['date'], self.day)
        self.assertEqual(result['digest_path'], self.day + '.md')
        self.assertEqual(result['package_path'], f'packages/{self.day}/')
        self.assertEqual(result['cutoff'], self.cutoff)
        self.assertEqual(result['digest_sha256'], hashlib.sha256(self.body).hexdigest())
        self.assertEqual((self.repo / result['digest_path']).read_bytes(), self.body)
        self.assertNotEqual(result['commit_sha'], pkg.git(self.repo, 'rev-parse', 'HEAD'))
        self.assertNotEqual(result['digest_commit'], result['commit_sha'])
        for name in ['manifest.json', 'incremental.jsonl', 'source_status.json', 'digest-pointer.json']:
            pkg.git(self.repo, 'cat-file', '-e', result['commit_sha'] + ':' + result['package_path'] + name)
        blob = subprocess.check_output(['git', '-C', str(self.repo), 'show', result['commit_sha'] + ':' + self.day + '.md'])
        self.assertEqual(hashlib.sha256(blob).hexdigest(), result['digest_sha256'])
        pointer = pkg.load(self.repo / 'packages' / self.day / 'digest-pointer.json')
        self.assertEqual(pointer['sha256'], result['digest_sha256'])
        self.assertEqual(pointer['commit_sha'], result['digest_commit'])
        self.assertEqual(self.other.read_bytes(), b'Earlier archive must stay byte-identical.\n')
        self.assertEqual(pkg.git(self.repo, 'status', '--porcelain'), '')
        self.assertNotIn('push', completed.stdout)

    def test_repeat_is_idempotent(self):
        first = self.publish()
        head = pkg.git(self.repo, 'rev-parse', 'HEAD')
        second = self.publish(expected_head=head)
        self.assertTrue(second['idempotent'])
        self.assertEqual(second['commit_sha'], first['commit_sha'])
        self.assertEqual(second['digest_sha256'], first['digest_sha256'])
        self.assertEqual(pkg.git(self.repo, 'rev-parse', 'HEAD'), head)

    def test_missing_or_invalid_input_does_not_publish(self):
        head = pkg.git(self.repo, 'rev-parse', 'HEAD')
        for body in (None, b'', b'   \n', b'\xff\xfe not utf-8'):
            with self.assertRaises(ValueError):
                self.publish(body=body)
        pkg.dump(self.snap / 'export-validation.json', {'status': 'FAIL', 'checks': {'bad': False}})
        with self.assertRaises(ValueError):
            self.publish()
        (self.snap / 'incremental.jsonl').unlink()
        with self.assertRaises(ValueError):
            self.publish()
        self.assertFalse((self.repo / (self.day + '.md')).exists())
        self.assertFalse((self.repo / 'packages' / 'latest.json').exists())
        self.assertEqual(pkg.git(self.repo, 'rev-parse', 'HEAD'), head)

    def test_refuses_existing_digest_overwrite_and_older_cutoff(self):
        self.publish()
        original = (self.repo / (self.day + '.md')).read_bytes()
        latest = (self.repo / 'packages' / 'latest.json').read_bytes()
        manifest = (self.repo / 'packages' / self.day / 'manifest.json').read_bytes()
        with self.assertRaises(ValueError):
            self.publish(body='不同的已定稿正文\n'.encode())
        self.cutoff = '2026-11-22T18:05:00+08:00'
        self.write_feed()
        with self.assertRaises(ValueError):
            self.publish(body='AI Builders Digest — 2026-11-22\n\n另一天。\n'.encode())
        self.assertEqual((self.repo / (self.day + '.md')).read_bytes(), original)
        self.assertEqual((self.repo / 'packages' / 'latest.json').read_bytes(), latest)
        self.assertEqual((self.repo / 'packages' / self.day / 'manifest.json').read_bytes(), manifest)
        self.assertEqual(self.other.read_bytes(), b'Earlier archive must stay byte-identical.\n')

    def test_refuses_main_dirty_head_mismatch_and_lock(self):
        subprocess.run(['git', '-C', str(self.repo), 'checkout', '-q', 'main'], check=True)
        with self.assertRaises(ValueError):
            self.publish()
        self.branch('other')
        (self.repo / 'notes.txt').write_text('dirty\n')
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
        self.assertFalse((self.repo / (self.day + '.md')).exists())
        self.assertEqual(pkg.git(self.repo, 'branch', '--show-current'), 'other')

    def test_changed_feed_revises_without_touching_original_package(self):
        self.publish()
        manifest = (self.repo / 'packages' / self.day / 'manifest.json').read_bytes()
        self.data[0]['title'] = 'Changed synthetic model research'
        self.write_feed()
        revised = self.publish()
        self.assertIn('/revisions/', revised['package_path'])
        self.assertEqual((self.repo / 'packages' / self.day / 'manifest.json').read_bytes(), manifest)
        self.assertEqual((self.repo / (self.day + '.md')).read_bytes(), self.body)
        self.assertEqual(revised['digest_sha256'], hashlib.sha256(self.body).hexdigest())

    def test_legacy_main_publisher_pointer_is_not_rewritten(self):
        subprocess.run(['git', '-C', str(self.repo), 'checkout', '-q', 'main'], check=True)
        (self.repo / (self.day + '.md')).write_bytes(self.body)
        self.commit_all('digest fixture')
        legacy = pkg.publish(self.feed, self.repo, push=False)
        head = pkg.git(self.repo, 'rev-parse', 'HEAD')
        stored = (self.repo / 'packages' / 'latest.json').read_bytes()
        self.branch('adopt')
        result = self.publish()
        self.assertTrue(result['idempotent'])
        self.assertEqual(result['commit_sha'], legacy['commit_sha'])
        self.assertNotIn('digest_sha256', json.loads(stored))
        self.assertEqual((self.repo / 'packages' / 'latest.json').read_bytes(), stored)
        self.assertEqual(pkg.git(self.repo, 'rev-parse', 'HEAD'), head)

    def test_private_body_and_mismatched_date_are_rejected(self):
        head = pkg.git(self.repo, 'rev-parse', 'HEAD')
        with self.assertRaises(ValueError):
            self.publish(body='See /Users/test/private.md\n'.encode())
        with self.assertRaises(ValueError):
            self.publish(digest_date='2026-11-25')
        self.assertFalse((self.repo / (self.day + '.md')).exists())
        self.assertEqual(pkg.git(self.repo, 'rev-parse', 'HEAD'), head)

    def test_empty_package_placeholder_is_not_replaced(self):
        target = self.repo / 'packages' / self.day
        target.mkdir(parents=True)
        (target / 'incremental.jsonl').write_text('')
        pkg.dump(target / 'manifest.json', {'status': 'ready'})
        self.commit_all('empty placeholder')
        before = (target / 'manifest.json').read_bytes()
        head = pkg.git(self.repo, 'rev-parse', 'HEAD')
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual((target / 'manifest.json').read_bytes(), before)
        self.assertEqual(pkg.git(self.repo, 'rev-parse', 'HEAD'), head)


if __name__ == '__main__':
    unittest.main()
