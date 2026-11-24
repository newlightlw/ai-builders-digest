#!/usr/bin/env python3
"""Publish one finalized UTF-8 digest and its frozen package on a non-main branch.

The feed cleaning stays in tools/export_daily_package.py. This command only
adds the editorial body, the branch commit sequence, and the refusal checks
that the main-push exporter does not apply. It never pushes.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'export_daily_package', ROOT / 'tools' / 'export_daily_package.py')
pkg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pkg)

PACKAGE_FILES = ('manifest.json', 'digest-pointer.json', 'incremental.jsonl', 'source_status.json')


def lock_path(repo):
    key = hashlib.sha256(str(Path(repo).resolve()).encode()).hexdigest()[:16]
    return Path('/tmp') / f'digest-publish-{key}.lock'


def _body_bytes(body):
    if body is None:
        raise ValueError('Missing finalized digest body')
    if isinstance(body, str):
        try:
            raw = body.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise ValueError('Digest body is not UTF-8') from exc
    elif isinstance(body, (bytes, bytearray)):
        raw = bytes(body)
    else:
        raise ValueError('Missing finalized digest body')
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('Digest body is not UTF-8') from exc
    if not raw.strip():
        raise ValueError('Missing finalized digest body')
    return raw


def _aware(value):
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Missing cutoff') from exc
    if stamp.tzinfo is None:
        raise ValueError('Input cutoff is naive or future')
    return stamp


def _require_branch(repo, expected_head):
    branch = pkg.git(repo, 'branch', '--show-current')
    if branch in {'', 'main'}:
        raise ValueError('Limited publish requires a clean non-main branch')
    dirty = pkg.git(repo, 'status', '--porcelain')
    if dirty:
        raise ValueError('Limited publish requires a clean worktree')
    head = pkg.git(repo, 'rev-parse', 'HEAD')
    if expected_head and expected_head != head:
        raise ValueError('Concurrent publish conflict: HEAD moved')
    return head


def _frozen_feed(feed):
    feed = Path(feed)
    pointer_path = feed / 'latest.json'
    if not pointer_path.is_file():
        raise ValueError('Missing frozen feed pointer')
    try:
        pointer = pkg.load(pointer_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('Missing frozen feed pointer') from exc
    if pointer.get('status') != 'ready':
        raise ValueError('Input pointer is not ready')
    snap = Path(pointer.get('snapshot') or '')
    for name in ('manifest.json', 'incremental.jsonl', 'source_status.json',
                 'export-validation.json', 'catalog.jsonl'):
        if not (snap / name).is_file():
            raise ValueError('Missing frozen input ' + name)
    try:
        meta = pkg.load(snap / 'manifest.json')
        proof = pkg.load(snap / 'export-validation.json')
        statuses = pkg.load(snap / 'source_status.json')
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('Missing or unreadable frozen input') from exc
    checks = proof.get('checks')
    if proof.get('status') != 'PASS' or not isinstance(checks, dict) or not checks or any(v is not True for v in checks.values()):
        raise ValueError('Input export validation has not passed')
    if not isinstance(statuses, list) or not statuses:
        raise ValueError('Missing frozen source status')
    cutoff = meta.get('cutoff')
    if not cutoff:
        raise ValueError('Missing cutoff')
    stamp = _aware(cutoff)
    if stamp > datetime.now(stamp.tzinfo):
        raise ValueError('Input cutoff is naive or future')
    if not (snap / 'incremental.jsonl').read_text().strip():
        raise ValueError('Missing frozen incremental')
    day = stamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    return day, cutoff, snap


def _fingerprint(repo, snap):
    policy = Path(repo) / 'tools' / 'source_policy.json'
    if not policy.is_file():
        raise ValueError('Missing source policy')
    material = pkg.checksum(snap / 'incremental.jsonl') + pkg.checksum(policy)
    return hashlib.sha256(material.encode()).hexdigest()


def _refuse_backward(repo, day, cutoff):
    path = Path(repo) / 'packages' / 'latest.json'
    if not path.is_file():
        return
    current = pkg.load(path)
    if current.get('status') != 'ready':
        return
    current_day = current.get('date')
    current_cutoff = current.get('cutoff')
    if (current_day and day < current_day) or (current_cutoff and _aware(cutoff) < _aware(current_cutoff)):
        raise ValueError('Refusing to move latest backward')


def _refuse_digest_conflict(repo, day, raw):
    path = Path(repo) / f'{day}.md'
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('Refusing to overwrite an existing digest')


def _refuse_package_conflict(repo, day, fingerprint, body_sha):
    base = Path(repo) / 'packages' / day
    manifest_path = base / 'manifest.json'
    if not manifest_path.is_file():
        return
    existing = pkg.load(manifest_path)
    if existing.get('input_fingerprint') == fingerprint:
        pointer_path = base / 'digest-pointer.json'
        pointer = pkg.load(pointer_path) if pointer_path.is_file() else {}
        if pointer.get('sha256') != body_sha:
            raise ValueError('Existing package digest pointer does not match the finalized body')
        return
    inc = base / 'incremental.jsonl'
    old = inc.read_text().strip() if inc.exists() else ''
    if old in {'', '[]'} and not existing.get('input_fingerprint'):
        raise ValueError('Refusing to replace an existing package')


def _already_published(repo, day, cutoff, raw, fingerprint, body_sha):
    repo = Path(repo)
    latest_path = repo / 'packages' / 'latest.json'
    digest = repo / f'{day}.md'
    if not latest_path.is_file() or not digest.is_file() or digest.read_bytes() != raw:
        return None
    latest = pkg.load(latest_path)
    package_path = latest.get('package_path') or ''
    relative = package_path.rstrip('/')
    if (latest.get('status') != 'ready' or latest.get('date') != day or latest.get('cutoff') != cutoff
            or latest.get('digest_path') != f'{day}.md' or not relative):
        return None
    if latest.get('digest_sha256') not in (None, body_sha):
        return None
    package = repo / relative
    if not (package / 'manifest.json').is_file() or not (package / 'digest-pointer.json').is_file():
        return None
    manifest = pkg.load(package / 'manifest.json')
    pointer = pkg.load(package / 'digest-pointer.json')
    if (manifest.get('status') != 'ready' or manifest.get('input_fingerprint') != fingerprint
            or manifest.get('date') != day or manifest.get('cutoff') != cutoff):
        return None
    if pointer.get('sha256') != body_sha or pointer.get('digest_path') != f'{day}.md' or pointer.get('date') != day:
        return None
    pkg.validate(package)
    commit = latest.get('commit_sha')
    head = pkg.git(repo, 'rev-parse', 'HEAD')
    if not commit or commit == head:
        return None
    ancestor = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', commit, head],
                              check=False, capture_output=True, text=True)
    if ancestor.returncode != 0:
        return None
    try:
        for name in PACKAGE_FILES:
            pkg.git(repo, 'cat-file', '-e', f'{commit}:{relative}/{name}')
        blob = subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:{day}.md'])
    except subprocess.CalledProcessError:
        return None
    if hashlib.sha256(blob).hexdigest() != body_sha:
        return None
    return latest


def _acquire(repo):
    path = lock_path(repo)
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                pid = int(path.read_text().strip())
            except (OSError, ValueError):
                pid = 0
            if pid > 0 and _alive(pid):
                raise ValueError('Concurrent publish conflict: lock held')
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return path
    raise ValueError('Concurrent publish conflict: lock held')


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _snapshot_packages(repo):
    root = Path(repo) / 'packages'
    found = {}
    if not root.exists():
        return found
    for path in root.rglob('*'):
        if path.is_file():
            found[path.relative_to(repo).as_posix()] = path.read_bytes()
    return found


def _assert_packages_unchanged(repo, before):
    for rel, data in before.items():
        if rel == 'packages/latest.json':
            continue
        path = Path(repo) / rel
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError('Refusing to alter an existing package file')


def _root_digests(repo):
    return {path.name: path.read_bytes() for path in Path(repo).glob('????-??-??.md')}


def _assert_roots(repo, before, day, raw):
    after = _root_digests(repo)
    for name, data in before.items():
        if name == f'{day}.md':
            if data != raw:
                raise ValueError('Refusing to overwrite an existing digest')
        elif after.get(name) != data:
            raise ValueError('Root daily archives changed')
    if after.get(f'{day}.md') != raw:
        raise ValueError('Published digest bytes mismatch')


def _git_run(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)


def _commit_paths(repo, paths, message):
    if not pkg.git(repo, 'status', '--porcelain', '--', *paths):
        return
    _git_run(repo, 'add', '--', *paths)
    _git_run(repo, 'commit', '-m', message)


def _ensure_digest_committed(repo, day, raw):
    path = Path(repo) / f'{day}.md'
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('Refusing to overwrite an existing digest')
    if not path.exists():
        path.write_bytes(raw)
    _commit_paths(repo, [f'{day}.md'], f'digest: {day}')


def _assert_feed_builds(feed, repo):
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / 'repo'
        subprocess.run(['git', 'clone', '--quiet', str(repo), str(clone)], check=True, capture_output=True, text=True)
        try:
            pkg.build(feed, clone)
        except json.JSONDecodeError as exc:
            raise ValueError('Missing or unreadable frozen input') from exc


def _verify_and_point(repo, target, day, cutoff, body_sha):
    repo = Path(repo)
    relative = Path(target).relative_to(repo).as_posix()
    manifest = pkg.validate(target)
    pointer = pkg.load(Path(target) / 'digest-pointer.json')
    if manifest.get('date') != day or manifest.get('cutoff') != cutoff or manifest.get('status') != 'ready':
        raise ValueError('Package date, cutoff, or status mismatch')
    if pointer.get('date') != day or pointer.get('digest_path') != f'{day}.md' or pointer.get('sha256') != body_sha:
        raise ValueError('Digest date, path, or SHA-256 mismatch')
    commit = pkg.git(repo, 'log', '-1', '--format=%H', '--', relative + '/manifest.json')
    if not commit:
        raise ValueError('Missing package commit')
    for name in PACKAGE_FILES:
        pkg.git(repo, 'cat-file', '-e', f'{commit}:{relative}/{name}')
    blob = subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:{day}.md'])
    if hashlib.sha256(blob).hexdigest() != body_sha:
        raise ValueError('Committed digest SHA-256 mismatch')
    digest_commit = pointer.get('commit_sha')
    if not digest_commit:
        raise ValueError('Missing digest commit pointer')
    pkg.git(repo, 'cat-file', '-e', f'{digest_commit}:{day}.md')
    latest = {
        'date': day,
        'status': 'ready',
        'commit_sha': commit,
        'digest_path': f'{day}.md',
        'digest_sha256': body_sha,
        'digest_commit': digest_commit,
        'package_path': relative + '/',
        'cutoff': cutoff,
    }
    latest_path = repo / 'packages' / 'latest.json'
    current = pkg.load(latest_path) if latest_path.is_file() else None
    if current != latest:
        _refuse_backward(repo, day, cutoff)
        pkg.dump(latest_path, latest)
        _commit_paths(repo, ['packages/latest.json'], 'packages: point readers at immutable validated package')
    head = pkg.git(repo, 'rev-parse', 'HEAD')
    if head == latest['commit_sha']:
        raise ValueError('Latest commit pointer aliases the package commit')
    stored = pkg.load(latest_path)
    if (stored.get('commit_sha') != latest['commit_sha'] or stored.get('digest_sha256') != body_sha
            or stored.get('date') != day or stored.get('digest_path') != f'{day}.md'
            or stored.get('package_path') != relative + '/' or stored.get('cutoff') != cutoff
            or stored.get('status') != 'ready'):
        raise ValueError('Authoritative latest does not match the published package')
    return stored


def publish_limited(repo, *, body, feed_root, expected_head=None, digest_date=None):
    repo = Path(repo)
    raw = _body_bytes(body)
    if pkg.PRIVATE.search(raw.decode('utf-8')):
        raise ValueError('Digest body contains a private pattern')
    day, cutoff, snap = _frozen_feed(feed_root)
    if digest_date is not None and digest_date != day:
        raise ValueError('Digest date must match the frozen cutoff date in Asia/Shanghai')
    fingerprint = _fingerprint(repo, snap)
    body_sha = hashlib.sha256(raw).hexdigest()
    _require_branch(repo, expected_head)
    _refuse_backward(repo, day, cutoff)
    _refuse_digest_conflict(repo, day, raw)
    _refuse_package_conflict(repo, day, fingerprint, body_sha)
    existing = _already_published(repo, day, cutoff, raw, fingerprint, body_sha)
    if existing is not None:
        result = dict(existing)
        result['digest_sha256'] = body_sha
        result['idempotent'] = True
        return result
    lock = _acquire(repo)
    try:
        _require_branch(repo, expected_head)
        before_packages = _snapshot_packages(repo)
        before_roots = _root_digests(repo)
        _assert_feed_builds(feed_root, repo)
        _ensure_digest_committed(repo, day, raw)
        target = pkg.build(feed_root, repo)
        _assert_packages_unchanged(repo, before_packages)
        _commit_paths(repo, [f'packages/{day}'], f'packages: export validated public metadata for {day}')
        stored = _verify_and_point(repo, target, day, cutoff, body_sha)
        _assert_roots(repo, before_roots, day, raw)
        if pkg.git(repo, 'status', '--porcelain'):
            raise ValueError('Publish left a dirty worktree')
        result = dict(stored)
        result['idempotent'] = False
        return result
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feed-root', type=Path, required=True)
    parser.add_argument('--body', type=Path, required=True, help='Finalized UTF-8 digest markdown')
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--expected-head')
    parser.add_argument('--date', help='Optional digest date; must equal the cutoff date in Asia/Shanghai')
    args = parser.parse_args(argv)
    try:
        raw = args.body.read_bytes()
    except OSError:
        print('Missing finalized digest body', file=sys.stderr)
        return 2
    try:
        result = publish_limited(args.repo, body=raw, feed_root=args.feed_root,
                                 expected_head=args.expected_head, digest_date=args.date)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
