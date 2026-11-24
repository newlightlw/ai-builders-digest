import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'tools/export_daily_package.py'
spec = importlib.util.spec_from_file_location('packager', MODULE)
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)

class PackageTests(unittest.TestCase):
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
        self.day = '2026-11-23'
        (self.repo / (self.day + '.md')).write_text('Existing archive must remain byte-identical.\n')
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.repo)], check=True)
        pkg.git(self.repo, 'config', 'user.name', 'Package Test')
        pkg.git(self.repo, 'config', 'user.email', 'test@example.invalid')
        self.commit()
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
        self.input()

    def commit(self):
        pkg.git(self.repo, 'add', '.')
        pkg.git(self.repo, 'commit', '-qm', 'synthetic fixture')

    def input(self):
        text = ''.join(json.dumps(r) + '\n' for r in self.data)
        (self.snap / 'catalog.jsonl').write_text(text)
        (self.snap / 'incremental.jsonl').write_text(text)
        pkg.dump(self.snap / 'manifest.json', {'cutoff': '2026-11-23T18:05:00+08:00', 'record_count': 3,
                 'incremental_count': 3, 'source_count': 3})
        pkg.dump(self.snap / 'export-validation.json', {'status': 'PASS', 'checks': {'synthetic_check': True}})
        pkg.dump(self.snap / 'source_status.json', [{'source_id': s, 'source_name': s, 'status': 'partial',
                 'retained_count': 1, 'cutoff': '2026-11-23T18:05:00+08:00', 'limitations': []}
                 for s in ['official', 'papers', 'noise']])
        pkg.dump(self.feed / 'latest.json', {'status': 'ready', 'cutoff': '2026-11-23T18:05:00+08:00', 'snapshot': str(self.snap)})

    def test_exact_identity_dedup_preserves_dates_and_evidence_ids(self):
        target = pkg.build(self.feed, self.repo)
        data = pkg.rows(target / 'incremental.jsonl')
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['record_id'], 'R-one')
        self.assertEqual(data[0]['also_record_ids'], ['R-two'])
        self.assertEqual(data[0]['published_on'], '2026-11-23')
        self.assertEqual(data[0]['published_at'], None)
        self.assertEqual(len(pkg.load(target / 'source_status.json')), 3)

    def test_unready_or_failed_input_keeps_existing_pointer(self):
        (self.repo / 'packages').mkdir()
        pkg.dump(self.repo / 'packages/latest.json', {'status': 'old_valid'})
        before = (self.repo / 'packages/latest.json').read_bytes()
        pkg.dump(self.snap / 'export-validation.json', {'status': 'FAIL', 'checks': {'bad': False}})
        with self.assertRaises(ValueError):
            pkg.build(self.feed, self.repo)
        self.assertEqual((self.repo / 'packages/latest.json').read_bytes(), before)

    def test_publication_anchor_exists_and_root_archive_is_unchanged(self):
        before = (self.repo / (self.day + '.md')).read_bytes()
        latest = pkg.publish(self.feed, self.repo)
        target = latest['package_path']
        self.assertNotEqual(latest['commit_sha'], pkg.git(self.repo, 'rev-parse', 'HEAD'))
        for name in ['manifest.json', 'incremental.jsonl', 'source_status.json', 'digest-pointer.json']:
            pkg.git(self.repo, 'cat-file', '-e', latest['commit_sha'] + ':' + target + name)
        self.assertEqual(before, (self.repo / (self.day + '.md')).read_bytes())
        first = pkg.git(self.repo, 'rev-parse', 'HEAD')
        self.assertEqual(latest, pkg.publish(self.feed, self.repo))
        self.assertEqual(first, pkg.git(self.repo, 'rev-parse', 'HEAD'))

    def test_real_package_is_not_overwritten_when_inputs_change(self):
        target = pkg.build(self.feed, self.repo)
        before = (target / 'manifest.json').read_bytes()
        self.data[0]['title'] = 'Changed synthetic model research'
        self.input()
        revision = pkg.build(self.feed, self.repo)
        self.assertIn('revisions', revision.parts)
        self.assertEqual((target / 'manifest.json').read_bytes(), before)

    def test_credentials_and_local_urls_are_rejected(self):
        for value in ['https://user:password@example.com/x', 'http://127.0.0.1/x',
                      'https://example.com/x?api_key=secret', 'http://192.168.1.1/x']:
            with self.assertRaises(ValueError):
                pkg.public_url(value)
        self.assertEqual(pkg.public_url('https://example.com/a?utm_source=x&id=1'), 'https://example.com/a?id=1')

    def test_private_text_never_enters_public_package(self):
        self.data[0]['title'] = 'Private file /Users/test/private.md'
        self.input()
        target = pkg.build(self.feed, self.repo)
        self.assertNotIn('/Users/', (target / 'incremental.jsonl').read_text())
        self.assertGreater(pkg.load(target / 'manifest.json')['filtered_counts']['private_pattern'], 0)

    def test_hash_tampering_is_detected(self):
        target = pkg.build(self.feed, self.repo)
        (target / 'incremental.jsonl').write_text('')
        with self.assertRaises(ValueError):
            pkg.validate(target)

if __name__ == '__main__':
    unittest.main()
