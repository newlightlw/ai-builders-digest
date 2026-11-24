#!/usr/bin/env python3
"""Attach a finalized morning issue to an already validated package.

The issue date is the Beijing publication date. The source is the previous
ready package pinned by packages/latest.json. This command does not collect,
does not read a feed-root, and does not create a new collection package.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    'export_daily_package', ROOT / 'tools' / 'export_daily_package.py')
pkg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pkg)

SHANGHAI = ZoneInfo('Asia/Shanghai')
PACKAGE_FILES = ('manifest.json', 'digest-pointer.json', 'incremental.jsonl', 'source_status.json')
HASHED_FILES = ('digest-pointer.json', 'incremental.jsonl', 'source_status.json')
LAG_LIMIT = timedelta(hours=36)
LAG_NOTICE = (
    '发布时刻晚于冻结截止超过36小时。覆盖范围仍是该冻结批次的全部增量与来源状态，'
    '没有因滞后删减来源或条目。'
)
RELATIONSHIP = (
    'publication_date 是北京时间早报发布日；source_date 与 source_cutoff 是前一晚已验证的'
    '冻结日包，不是新采集。'
)


def lock_path(repo):
    key = hashlib.sha256(str(Path(repo).resolve()).encode()).hexdigest()[:16]
    return Path('/tmp') / f'digest-publish-{key}.lock'


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def _git_run(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True)


def _blob(repo, commit, path):
    try:
        return subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:{path}'])
    except subprocess.CalledProcessError as exc:
        raise ValueError('缺少冻结日包文件：' + path) from exc


def _body_bytes(body):
    if body is None:
        raise ValueError('缺少已定稿正文')
    if isinstance(body, str):
        try:
            raw = body.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise ValueError('正文不是 UTF-8') from exc
    elif isinstance(body, (bytes, bytearray)):
        raw = bytes(body)
    else:
        raise ValueError('缺少已定稿正文')
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('正文不是 UTF-8') from exc
    if not raw.strip():
        raise ValueError('缺少已定稿正文')
    return raw


def _clock(now):
    if now is None:
        return datetime.now(SHANGHAI)
    if isinstance(now, str):
        try:
            now = datetime.fromisoformat(now)
        except ValueError as exc:
            raise ValueError('时钟无效') from exc
    if now.tzinfo is None:
        raise ValueError('时钟没有时区')
    return now


def _calendar_day(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError('发布日必须是 YYYY-MM-DD')
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError('发布日必须是 YYYY-MM-DD') from exc


def _aware(value):
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('缺少截止时间') from exc
    if stamp.tzinfo is None:
        raise ValueError('截止时间没有时区')
    return stamp


def _require_branch(repo, expected_head):
    branch = _git(repo, 'branch', '--show-current')
    if branch in {'', 'main'}:
        raise ValueError('限定发布必须在干净的非 main 分支上')
    if _git(repo, 'status', '--porcelain'):
        raise ValueError('限定发布必须在干净的非 main 分支上')
    head = _git(repo, 'rev-parse', 'HEAD')
    if expected_head and expected_head != head:
        raise ValueError('并发冲突：HEAD 已变化')
    return head


def inspect_frozen_source(repo, now=None):
    """Read the ready package pinned by latest.json. Does not write or collect."""
    repo = Path(repo)
    now = _clock(now)
    latest_path = repo / 'packages' / 'latest.json'
    if not latest_path.is_file():
        raise ValueError('缺少 packages/latest.json，不能把未取得的 feed 当成冻结源')
    latest = _load(latest_path)
    if latest.get('status') != 'ready':
        raise ValueError('latest 不是 ready，不能标成冻结源')
    commit = latest.get('commit_sha')
    package_path = latest.get('package_path') or ''
    relative = package_path.strip('/')
    cutoff = latest.get('cutoff')
    if not commit or not relative or not cutoff:
        raise ValueError('latest 缺少冻结提交、路径或截止时间')
    ancestor = subprocess.run(
        ['git', '-C', str(repo), 'merge-base', '--is-ancestor', commit, 'HEAD'],
        check=False, capture_output=True, text=True)
    if ancestor.returncode != 0:
        raise ValueError('冻结源提交不在当前分支历史上')
    blobs = {name: _blob(repo, commit, f'{relative}/{name}') for name in PACKAGE_FILES}
    for name in PACKAGE_FILES:
        work = repo / relative / name
        if not work.is_file() or work.read_bytes() != blobs[name]:
            raise ValueError('工作区日包与冻结提交不一致')
    try:
        manifest = json.loads(blobs['manifest.json'])
        pointer = json.loads(blobs['digest-pointer.json'])
        statuses = json.loads(blobs['source_status.json'])
    except json.JSONDecodeError as exc:
        raise ValueError('冻结日包无法解析，不能标成 ready') from exc
    if manifest.get('status') != 'ready':
        raise ValueError('冻结 manifest 不是 ready')
    if manifest.get('cutoff') != cutoff or manifest.get('date') != latest.get('date'):
        raise ValueError('latest 与冻结 manifest 的日期或截止时间不一致')
    stamp = _aware(cutoff)
    if stamp > now:
        raise ValueError('拒绝未来截止时间')
    source_day = stamp.astimezone(SHANGHAI).date()
    if manifest.get('date') != source_day.isoformat():
        raise ValueError('冻结源日期与截止时间的北京时间日期不一致')
    if f'packages/{source_day.isoformat()}/' not in (relative + '/'):
        raise ValueError('冻结源路径与批次日期不一致')
    files = manifest.get('files')
    if not isinstance(files, dict):
        raise ValueError('冻结 manifest 缺少文件哈希')
    for name in HASHED_FILES:
        proof = files.get(name) or {}
        if proof.get('sha256') != _sha256(blobs[name]):
            raise ValueError('冻结源哈希与 manifest 不一致')
    lines = [line for line in blobs['incremental.jsonl'].decode('utf-8').splitlines() if line.strip()]
    try:
        for line in lines:
            json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError('增量无法解析，不能标成 ready') from exc
    if not lines or manifest.get('clean_incremental_count') != len(lines):
        raise ValueError('缺少增量或计数不一致，不能标成 ready')
    if not isinstance(statuses, list) or not statuses:
        raise ValueError('缺少来源状态，不能标成 ready')
    total = 0
    for item in statuses:
        if not item.get('source_id') or not item.get('status'):
            raise ValueError('来源状态缺少 source_id 或 status，不能标成 ready')
        total += item.get('package_incremental_count', 0)
    if total != len(lines):
        raise ValueError('来源状态计数与增量不一致，不能标成 ready')
    archived = pointer.get('digest_path')
    if pointer.get('sha256') and archived:
        if _sha256(_blob(repo, commit, archived)) != pointer['sha256']:
            raise ValueError('冻结源正文指针哈希不一致')
    return {
        'source_commit_sha': commit,
        'source_package_path': relative + '/',
        'source_date': source_day.isoformat(),
        'source_cutoff': cutoff,
        'source_manifest_sha256': _sha256(blobs['manifest.json']),
        'clean_incremental_count': len(lines),
        'incremental_lines': len(lines),
        'source_status_count': len(statuses),
    }


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


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
                raise ValueError('并发冲突：已有发布锁')
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return path
    raise ValueError('并发冲突：已有发布锁')


def _record_for(repo, publication_day, raw, source, now):
    pub = publication_day.isoformat()
    stamp = _aware(source['source_cutoff'])
    lag = now - stamp
    over_limit = lag > LAG_LIMIT
    notice = LAG_NOTICE if over_limit else None
    return {
        'schema_version': 'daily-publication/1',
        'status': 'ready',
        'publication_date': pub,
        'digest_path': pub + '.md',
        'digest_sha256': _sha256(raw),
        'digest_commit': None,
        'source_date': source['source_date'],
        'source_cutoff': source['source_cutoff'],
        'source_commit_sha': source['source_commit_sha'],
        'source_package_path': source['source_package_path'],
        'source_manifest_sha256': source['source_manifest_sha256'],
        'source_role': 'frozen_validated_package',
        'collection_created': False,
        'relationship': RELATIONSHIP,
        'coverage': {
            'clean_incremental_count': source['clean_incremental_count'],
            'incremental_lines': source['incremental_lines'],
            'source_status_count': source['source_status_count'],
        },
        'lag_over_36h': over_limit,
        'lag_hours': round(lag.total_seconds() / 3600, 4),
        'lag_notice': notice,
    }


def _refuse_issue_rules(repo, publication_day, raw, source, now):
    repo = Path(repo)
    pub = publication_day.isoformat()
    source_day = source['source_date']
    today = now.astimezone(SHANGHAI).date()
    if publication_day > today:
        raise ValueError('拒绝发布未来的早报日期')
    if publication_day.isoformat() <= source_day:
        raise ValueError('发布日必须晚于冻结源批次日期')
    if f'packages/{pub}/' in source['source_package_path']:
        raise ValueError('拒绝把发布写成新的采集日包')
    digest = repo / f'{pub}.md'
    if digest.exists() and digest.read_bytes() != raw:
        raise ValueError('拒绝覆盖已有日期正文')
    per_date = repo / 'packages' / 'publications' / f'{pub}.json'
    if per_date.is_file():
        stored = _load(per_date)
        if stored.get('digest_sha256') != _sha256(raw) or stored.get('source_commit_sha') != source['source_commit_sha']:
            raise ValueError('拒绝覆盖已有日期正文')
    latest = repo / 'packages' / 'publication-latest.json'
    if latest.is_file():
        current = _load(latest)
        current_day = current.get('publication_date')
        if current_day and current_day > pub:
            raise ValueError('拒绝把发布指针退回更早的日期')
        if current_day == pub and (
                current.get('digest_sha256') != _sha256(raw)
                or current.get('source_commit_sha') != source['source_commit_sha']):
            raise ValueError('拒绝覆盖已有日期正文')


def _same_publication(repo, record, raw, source):
    repo = Path(repo)
    path = repo / 'packages' / 'publications' / f"{record['publication_date']}.json"
    latest = repo / 'packages' / 'publication-latest.json'
    digest = repo / record['digest_path']
    if not path.is_file() or not latest.is_file() or not digest.is_file() or digest.read_bytes() != raw:
        return None
    stored = _load(path)
    pointed = _load(latest)
    body_sha = _sha256(raw)
    if stored != pointed:
        return None
    if (stored.get('status') != 'ready' or stored.get('collection_created') is not False
            or stored.get('publication_date') != record['publication_date']
            or stored.get('digest_sha256') != body_sha
            or stored.get('source_commit_sha') != source['source_commit_sha']
            or stored.get('source_cutoff') != source['source_cutoff']
            or stored.get('source_date') != source['source_date']
            or stored.get('source_package_path') != source['source_package_path']):
        return None
    coverage = stored.get('coverage') or {}
    if (coverage.get('clean_incremental_count') != source['clean_incremental_count']
            or coverage.get('incremental_lines') != source['incremental_lines']
            or coverage.get('source_status_count') != source['source_status_count']):
        return None
    commit = stored.get('digest_commit')
    if not commit:
        return None
    try:
        blob = _blob(repo, commit, stored['digest_path'])
    except ValueError:
        return None
    if blob != raw:
        return None
    return stored


def _snapshot(repo):
    found = {}
    for path in Path(repo).glob('????-??-??.md'):
        found[path.name] = path.read_bytes()
    packages = Path(repo) / 'packages'
    if packages.exists():
        for path in packages.rglob('*'):
            if path.is_file():
                found[path.relative_to(repo).as_posix()] = path.read_bytes()
    return found


def _assert_frozen_files(repo, before, publication_day):
    pub = publication_day.isoformat()
    allowed = {
        pub + '.md',
        f'packages/publications/{pub}.json',
        'packages/publication-latest.json',
    }
    after = _snapshot(repo)
    for rel, data in before.items():
        if rel == 'packages/publication-latest.json':
            continue
        if after.get(rel) != data:
            raise ValueError('拒绝改写不可变日包或历史日报')
    for rel in after:
        if rel not in before and rel not in allowed:
            raise ValueError('拒绝把发布写成新的采集日包')
    if (Path(repo) / 'packages' / pub / 'manifest.json').exists():
        raise ValueError('拒绝把发布写成新的采集日包')


def _ensure_digest(repo, publication_day, raw):
    path = Path(repo) / f'{publication_day.isoformat()}.md'
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('拒绝覆盖已有日期正文')
    if not path.exists():
        path.write_bytes(raw)
    rel = path.name
    if _git(repo, 'status', '--porcelain', '--', rel):
        _git_run(repo, 'add', '--', rel)
        _git_run(repo, 'commit', '-m', f'digest: {publication_day.isoformat()}')
    commit = _git(repo, 'log', '-1', '--format=%H', '--', rel)
    if not commit or _blob(repo, commit, rel) != raw:
        raise ValueError('正文提交与已定稿字节不一致')
    return commit


def publish_limited(repo, *, body, publication_date, expected_head=None, now=None):
    repo = Path(repo)
    raw = _body_bytes(body)
    if pkg.PRIVATE.search(raw.decode('utf-8')):
        raise ValueError('正文含有不应公开的本地路径或凭证样式')
    now = _clock(now)
    publication_day = _calendar_day(publication_date)
    _require_branch(repo, expected_head)
    source = inspect_frozen_source(repo, now=now)
    _refuse_issue_rules(repo, publication_day, raw, source, now)
    draft = _record_for(repo, publication_day, raw, source, now)
    existing = _same_publication(repo, draft, raw, source)
    if existing is not None:
        result = dict(existing)
        result['idempotent'] = True
        return result
    lock = _acquire(repo)
    try:
        _require_branch(repo, expected_head)
        source = inspect_frozen_source(repo, now=now)
        _refuse_issue_rules(repo, publication_day, raw, source, now)
        draft = _record_for(repo, publication_day, raw, source, now)
        existing = _same_publication(repo, draft, raw, source)
        if existing is not None:
            result = dict(existing)
            result['idempotent'] = True
            return result
        before = _snapshot(repo)
        digest_commit = _ensure_digest(repo, publication_day, raw)
        record = _record_for(repo, publication_day, raw, source, now)
        record['digest_commit'] = digest_commit
        if (record['collection_created'] or record['source_commit_sha'] != source['source_commit_sha']
                or record['coverage']['incremental_lines'] != source['incremental_lines']):
            raise ValueError('拒绝把发布写成新的采集日包')
        if record['lag_over_36h'] and not record['lag_notice']:
            raise ValueError('超过36小时仍缺少滞后提示')
        per_date = repo / 'packages' / 'publications' / f'{publication_day.isoformat()}.json'
        latest = repo / 'packages' / 'publication-latest.json'
        _dump(per_date, record)
        _dump(latest, record)
        _git_run(repo, 'add', '--', per_date.relative_to(repo).as_posix(), 'packages/publication-latest.json')
        _git_run(repo, 'commit', '-m',
                 f"packages: record publication {publication_day.isoformat()} against frozen source {source['source_date']}")
        _assert_frozen_files(repo, before, publication_day)
        if _git(repo, 'status', '--porcelain'):
            raise ValueError('发布后工作区不干净')
        stored = _load(latest)
        if (stored.get('publication_date') != publication_day.isoformat()
                or stored.get('source_date') != source['source_date']
                or stored.get('source_cutoff') != source['source_cutoff']
                or stored.get('source_commit_sha') != source['source_commit_sha']
                or stored.get('digest_sha256') != _sha256(raw)
                or stored.get('collection_created') is not False
                or stored.get('status') != 'ready'):
            raise ValueError('发布记录没有同时写明发布日和冻结源')
        if _git(repo, 'rev-parse', 'HEAD') == stored['source_commit_sha']:
            raise ValueError('冻结源提交被发布提交替换')
        result = dict(stored)
        result['idempotent'] = False
        return result
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body', type=Path, required=True, help='已定稿 UTF-8 早报')
    parser.add_argument('--publication-date', required=True, help='北京时间发布日 YYYY-MM-DD')
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--expected-head')
    parser.add_argument('--now', help='仅隔离测试使用的带时区时钟；正式调用不要传')
    parser.add_argument('--feed-root', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.feed_root is not None:
        print('本路径不读取 feed-root，也没有可用的 validated/public-feed。'
              '请提供 --body 与 --publication-date。源是 packages/latest.json 所钉的不可变日包四文件。',
              file=sys.stderr)
        return 2
    try:
        raw = args.body.read_bytes()
    except OSError:
        print('缺少已定稿正文', file=sys.stderr)
        return 2
    try:
        result = publish_limited(
            args.repo, body=raw, publication_date=args.publication_date,
            expected_head=args.expected_head, now=args.now)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
