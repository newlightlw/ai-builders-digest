#!/usr/bin/env python3
"""Export validated public source metadata; optionally publish immutable Git packages."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
PRIVATE = re.compile(r'/Users/|/root/|/private/var/|Bearer\s+\S+|\b(?:oc|ou)_[0-9a-f]{16,}|\bsk-[A-Za-z0-9_-]{16,}', re.I)
AI = re.compile(r'\b(?:AI|AGI|LLM|GPT|Claude|Gemini|agent|agents|robot|robotics|NVIDIA|OpenAI|Anthropic|Qwen|DeepSeek|diffusion|inference|transformer)\b|人工智能|智能体|大模型|多模态|具身|机器人|生成式|千问|混元|元宝|豆包|智谱|可灵|蒸馏', re.I)
DATE_FIELDS = 'published_at_raw published_at published_on updated_at_raw updated_at updated_on discovered_at fetched_at date_role date_precision'.split()

def load(path):
    return json.loads(Path(path).read_text())

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

def public_url(value):
    if not value:
        return None
    p = urlsplit(value)
    if p.scheme not in {'https', 'http'} or not p.hostname or p.username or p.password:
        raise ValueError('Not a public HTTP URL')
    host = p.hostname.lower()
    if host in {'localhost', 'localhost.localdomain'} or host.endswith(('.local', '.internal')):
        raise ValueError('Local host is not public')
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None
    if addr and not addr.is_global:
        raise ValueError('Non-public IP')
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    if any(re.search(r'token|secret|password|api[_-]?key|authorization', k, re.I) for k, _ in query):
        raise ValueError('Credential-like URL query')
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(query), p.fragment))

def identity(url):
    match = re.search(r'(?:arxiv.org/(?:abs|pdf)/|huggingface.co/papers/)(\d{4}\.\d{4,5})', url)
    if match:
        return 'arxiv:' + match[1]
    p = urlsplit(url)
    return urlunsplit(('https', p.netloc.lower().removeprefix('www.'), p.path.rstrip('/') or '/', p.query, p.fragment))

def clean_status(st, decision, count):
    notes = ' '.join(st.get('limitations', []))
    issues = []
    for pattern, label in [(r'429|Too Many Requests', 'rate_limited_429'), (r'403|Forbidden', 'access_restricted_403'),
                           (r'405', 'request_rejected_405'), (r'SSLError|SSLEOFError|TLS', 'tls_error'),
                           (r'timed out', 'network_timeout'), (r'no_matching_sitemap', 'sitemap_rules_no_match'),
                           (r'no_verified_item', 'no_verified_items'), (r'prior captured', 'older_capture_only')]:
        if re.search(pattern, notes, re.I):
            issues.append(label)
    if st['status'] in {'partial', 'empty_partial'}:
        issues.append('available_inventory_not_complete_history')
    if st['status'] == 'blocked':
        issues.append('disabled_by_existing_access_policy')
    return {'source_id': st['source_id'], 'name': st['source_name'], 'status': st['status'],
            'history_coverage': st.get('history_coverage'), 'input_count': st['retained_count'],
            'package_incremental_count': count, 'source_decision': decision,
            'window_start': st.get('window_start'), 'cutoff': st['cutoff'], 'issues': issues}

def build(feed, repo=REPO):
    feed, repo = Path(feed), Path(repo)
    pointer = load(feed / 'latest.json')
    if pointer.get('status') != 'ready':
        raise ValueError('Input pointer is not ready')
    snap = Path(pointer['snapshot'])
    meta, proof = load(snap / 'manifest.json'), load(snap / 'export-validation.json')
    if proof.get('status') != 'PASS' or not proof.get('checks') or not all(v is True for v in proof['checks'].values()):
        raise ValueError('Input export validation has not passed')
    cutoff = datetime.fromisoformat(meta['cutoff'])
    if cutoff.tzinfo is None or cutoff > datetime.now(cutoff.tzinfo):
        raise ValueError('Input cutoff is naive or future')
    catalog, inc, statuses = rows(snap / 'catalog.jsonl'), rows(snap / 'incremental.jsonl'), load(snap / 'source_status.json')
    if len(catalog) != meta['record_count'] or len(inc) != meta['incremental_count'] or len(statuses) != meta['source_count']:
        raise ValueError('Input counts differ')
    if pointer['cutoff'] != meta['cutoff'] or len({r['record_id'] for r in catalog}) != len(catalog):
        raise ValueError('Input identity or cutoff mismatch')
    catalog_by_id = {r['record_id']: r for r in catalog}
    if any(r != catalog_by_id.get(r['record_id']) for r in inc):
        raise ValueError('Incremental is not an exact subset of catalog')
    policy = load(repo / 'tools/source_policy.json')
    by = {s['source_id']: s for s in policy['sources']}
    if len(by) != len(policy['sources']) or {s['source_id'] for s in statuses} != set(by):
        raise ValueError('Source policy does not cover the exact source set')
    dropped, candidates = Counter(), []
    rank = {'海外厂商与模型': 0, '国内厂商与模型': 0, '具身与物理AI': 0, '商业与披露': 1,
            '论文与研究': 1, '工程与开发实践': 1, '人物与组织判断': 2, '产品发现与玩法': 2}
    for r in inc:
        source = by[r['source_id']]
        if source['decision'] != 'keep':
            dropped['excluded_source'] += 1
            continue
        if r['material_status'] in {'navigation', 'shared_listing_text'} or r['effective_kind'] == 'documentation_link':
            dropped['navigation_or_shared_listing'] += 1
            continue
        if r['time_bucket'] == 'future_quarantine' or r.get('published_at') and datetime.fromisoformat(r['published_at']) > cutoff:
            raise ValueError('Future publication escaped quarantine')
        text = r.get('title', '')
        if source['group'] in {'独立媒体与产业', '产品发现与玩法'} or r['source_id'] == 'yahoo_finance':
            if not AI.search(text):
                dropped['no_explicit_ai_signal_in_title'] += 1
                continue
        try:
            url = public_url(r['url'])
        except ValueError:
            dropped['unsafe_url'] += 1
            continue
        row = {k: r.get(k) for k in ['record_id', 'source_id', 'source_name', 'title'] + DATE_FIELDS}
        row.update(url=url, group=source['group'], archive_change=r['archive_change'], material_status=r['material_status'],
                   effective_kind=r['effective_kind'], time_bucket=r['time_bucket'], fact_checked=False)
        if PRIVATE.search(json.dumps(row, ensure_ascii=False)):
            dropped['private_pattern'] += 1
            continue
        candidates.append((rank.get(source['group'], 3), row, identity(url)))
    # Exact URL/arXiv identity only. Original R IDs remain traceable; no semantic event claims.
    chosen, seen, counts = [], {}, Counter()
    for _, row, key in sorted(candidates, key=lambda x: (x[0], x[1]['source_id'], x[1]['record_id'])):
        if key in seen:
            seen[key].setdefault('also_record_ids', []).append(row['record_id'])
            dropped['exact_identity_duplicate'] += 1
            continue
        cap = policy['caps'].get(row['source_id'], policy['source_item_cap'])
        if counts[row['source_id']] >= cap:
            dropped['deferred_by_per_source_budget'] += 1
            continue
        row['identity_key'] = key
        chosen.append(row)
        seen[key] = row
        counts[row['source_id']] += 1
    day = cutoff.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
    digest = repo / (day + '.md')
    digest_hash = checksum(digest) if digest.exists() else None
    fingerprint = hashlib.sha256(((checksum(snap / 'incremental.jsonl')) + checksum(repo / 'tools/source_policy.json')).encode()).hexdigest()
    target = repo / 'packages' / day
    if (target / 'manifest.json').exists():
        existing = load(target / 'manifest.json')
        if existing.get('input_fingerprint') == fingerprint:
            validate(target)
            return target
        old = (target / 'incremental.jsonl').read_text().strip()
        if old not in {'', '[]'} or existing.get('input_fingerprint'):
            target = target / 'revisions' / (cutoff.strftime('%H%M%S') + '-' + fingerprint[:8])
            if target.exists():
                if load(target / 'manifest.json').get('input_fingerprint') == fingerprint:
                    validate(target)
                    return target
                raise ValueError('Immutable revision collision')
    target.mkdir(parents=True, exist_ok=True)
    (target / 'incremental.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in chosen))
    dump(target / 'source_status.json', [clean_status(st, by[st['source_id']]['decision'], counts[st['source_id']]) for st in statuses])
    digest_path = digest.name if digest.exists() else None
    base_commit = git(repo, 'rev-parse', 'HEAD')
    dump(target / 'digest-pointer.json', {'date': day, 'status': 'archived' if digest_path else 'pending_editor',
         'digest_path': digest_path, 'commit_sha': base_commit if digest_path else None, 'sha256': digest_hash,
         'relationship': 'existing_same_calendar_date_remix; not generated from this later collection package',
         'digest_cutoff': None, 'collection_cutoff': meta['cutoff']})
    files = {n: {'sha256': checksum(target / n), 'bytes': (target / n).stat().st_size}
             for n in ['incremental.jsonl', 'source_status.json', 'digest-pointer.json']}
    manifest = {'schema_version': 'clean-daily-package/1', 'date': day, 'status': 'ready', 'cutoff': meta['cutoff'],
                'created_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'input_fingerprint': fingerprint,
                'input_counts': {'records': len(catalog), 'incremental': len(inc), 'sources': len(statuses)},
                'retained_source_count': sum(s['decision'] == 'keep' for s in by.values()),
                'excluded_source_count': sum(s['decision'] != 'keep' for s in by.values()),
                'clean_incremental_count': len(chosen), 'source_counts': dict(counts), 'filtered_counts': dict(dropped),
                'input_export_validation': 'PASS', 'files': files,
                'limitations': ['首次入库不等于今日发布', '精确URL/arXiv归组不等于事件语义去重',
                                '标题过滤及每源预算是编辑召回策略，不能保证完整或事实正确',
                                '榜单、产品收录、发现、发布、更新和抓取时间各自保留',
                                'X转录不代表全量点赞或转发', '现有remix归档与新资料包的时间边界不同']}
    dump(target / 'manifest.json', manifest)
    validate(target)
    return target

def validate(target):
    target = Path(target)
    m, data, statuses = load(target / 'manifest.json'), rows(target / 'incremental.jsonl'), load(target / 'source_status.json')
    if m['status'] != 'ready' or m['clean_incremental_count'] != len(data):
        raise ValueError('Package is not valid/ready')
    for name, proof in m['files'].items():
        if Path(name).name != name or checksum(target / name) != proof['sha256']:
            raise ValueError('Package file hash mismatch')
    if len({r['record_id'] for r in data}) != len(data) or len({r['identity_key'] for r in data}) != len(data):
        raise ValueError('Duplicate package identity')
    if sum(s['package_incremental_count'] for s in statuses) != len(data):
        raise ValueError('Source status counts differ')
    for p in target.iterdir():
        if p.is_file() and PRIVATE.search(p.read_text()):
            raise ValueError('Private pattern in public package')
    return m

def publish(feed, repo=REPO, push=False):
    repo = Path(repo)
    if git(repo, 'branch', '--show-current') != 'main' or git(repo, 'status', '--porcelain'):
        raise ValueError('Publisher requires a clean main checkout')
    if push:
        origin = git(repo, 'remote', 'get-url', 'origin')
        if origin not in {'https://github.com/newlightlw/ai-builders-digest.git', 'git@github.com:newlightlw/ai-builders-digest.git'}:
            raise ValueError('Unexpected publication remote')
        subprocess.run(['git', '-C', str(repo), 'pull', '--ff-only', 'origin', 'main'], check=True)
    root_before = {p.name: checksum(p) for p in repo.glob('????-??-??.md')}
    target = build(feed, repo)
    relative = target.relative_to(repo).as_posix()
    if git(repo, 'status', '--porcelain'):
        subprocess.run(['git', '-C', str(repo), 'add', '--', relative], check=True)
        subprocess.run(['git', '-C', str(repo), 'commit', '-m', 'packages: export validated public metadata for ' + target.parts[-1]], check=True)
    commit = git(repo, 'log', '-1', '--format=%H', '--', relative + '/manifest.json')
    m = validate(target)
    digest = load(target / 'digest-pointer.json')['digest_path']
    latest = {'date': m['date'], 'status': 'ready', 'commit_sha': commit, 'digest_path': digest,
              'package_path': relative + '/', 'cutoff': m['cutoff']}
    # commit_sha names the immutable package commit, not this later pointer commit.
    for name in ['manifest.json', 'digest-pointer.json', 'incremental.jsonl', 'source_status.json']:
        git(repo, 'cat-file', '-e', commit + ':' + relative + '/' + name)
    if digest:
        git(repo, 'cat-file', '-e', commit + ':' + digest)
    if not (repo / 'packages/latest.json').exists() or load(repo / 'packages/latest.json') != latest:
        dump(repo / 'packages/latest.json', latest)
        subprocess.run(['git', '-C', str(repo), 'add', '--', 'packages/latest.json'], check=True)
        subprocess.run(['git', '-C', str(repo), 'commit', '-m', 'packages: point readers at immutable validated package'], check=True)
    if root_before != {p.name: checksum(p) for p in repo.glob('????-??-??.md')}:
        raise ValueError('Root daily archives changed')
    if push:
        subprocess.run(['git', '-C', str(repo), 'push', 'origin', 'main'], check=True)
    return latest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feed-root', type=Path, required=True)
    parser.add_argument('--publish', action='store_true', help='Commit package then pointer and push main; requires authorized Git credentials')
    args = parser.parse_args()
    result = publish(args.feed_root, push=True) if args.publish else {'package_path': str(build(args.feed_root))}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
