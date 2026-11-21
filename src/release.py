"""Fail-closed publishing decisions for the public Couponia catalog.

The Android app only reads cards.json, merchants.json and acceptance.json.
Their dataVersion MUST NOT change when only benefit candidates/metadata change.

This step reads an existing deployment *before* publishing. A network error is
never treated as an empty previous deployment (404 is the only exception).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Preserve the established CLI form: python src/release.py.
if __package__ in (None, ''):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.catalog_guard import assert_additive_records

CORE = ('cards.json', 'merchants.json', 'acceptance.json')
ENRICHMENTS = ('benefit_candidates.json', 'acceptance_candidates.json', 'sources.json')
MAX_BYTES = 10_000_000


def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(data):
    return hashlib.sha256(canonical(data)).hexdigest()


def normalize_enrichment(name, rows):
    if not isinstance(rows, list):
        raise ValueError(f'{name}: expected a JSON array')
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f'{name}: expected JSON objects')
    if name == 'sources.json':
        # A fresh import timestamp by itself is NOT a source data change.
        return [{k: v for k, v in row.items() if k != 'imported_at'} for row in rows]
    return rows


def enrichment_hash(files):
    return digest({name: normalize_enrichment(name, files[name]) for name in ENRICHMENTS})


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def fetch_json(url, optional_404=False, expected_sha=None):
    if not url.startswith('https://'):
        raise ValueError('Previous catalog URL must use HTTPS')
    req = Request(url, headers={'User-Agent':'couponia-catalog-release/1.0',
                                'Accept':'application/json'})
    try:
        with urlopen(req, timeout=25) as response:
            blob = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 404 and optional_404:
            return None
        raise
    if len(blob) > MAX_BYTES:
        raise ValueError('Previous catalog JSON too large')
    if expected_sha is not None and hashlib.sha256(blob).hexdigest() != expected_sha:
        raise ValueError('Previous catalog core checksum mismatch')
    return json.loads(blob)


def previous_from_url(base):
    """Download last successfully published catalog. Fail closed on errors."""
    base = base.rstrip('/')
    manifest = fetch_json(f'{base}/manifest.json', optional_404=True)
    if manifest is None:
        return None
    verify_manifest(manifest)
    files = {}
    for name in ENRICHMENTS:
        files[name] = fetch_json(f'{base}/{name}', optional_404=False)
    core = {name: fetch_json(f'{base}/{name}', expected_sha=manifest['fileSha256'][name])
            for name in CORE}
    return manifest, files, core


def previous_from_dir(folder):
    folder = Path(folder)
    manifest = folder / 'manifest.json'
    if not manifest.exists():
        return None
    metadata = read_json(manifest)
    verify_manifest(metadata)
    core = {}
    for name in CORE:
        raw = (folder / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != metadata['fileSha256'][name]:
            raise ValueError('Previous catalog core checksum mismatch')
        core[name] = json.loads(raw)
    return metadata, {name: read_json(folder / name) for name in ENRICHMENTS}, core


def verify_manifest(old):
    if not isinstance(old, dict) or old.get('schemaVersion') != 3:
        raise ValueError('Previous catalog manifest has an unsupported schemaVersion')
    if type(old.get('dataVersion')) is not int or old['dataVersion'] < 1:
        raise ValueError('Previous catalog dataVersion is not a valid integer')
    if not isinstance(old.get('fileSha256'), dict):
        raise ValueError('Previous catalog is missing core SHA-256 values')
    if any(not isinstance(old['fileSha256'].get(name), str) or
           not re.fullmatch(r'[0-9a-f]{64}', old['fileSha256'][name]) for name in CORE):
        raise ValueError('Previous catalog has invalid core checksums')


def version_after(old, proposed):
    return max(proposed, int(old) + 1) if old else proposed


def publication_decision(directory, previous, clock=None):
    """Adjust manifest + SQLite and return what should be published.

    Files are freshly built by src/build.py. None of this modifies the wallet.
    """
    directory = Path(directory)
    now = clock or datetime.now(timezone.utc)
    proposed_version = int(now.strftime('%Y%m%d%H%M%S'))
    current = read_json(directory / 'manifest.json')
    if current.get('schemaVersion') != 3:
        raise ValueError('Current catalog schemaVersion must be 3')
    new_extra = {name: read_json(directory / name) for name in ENRICHMENTS}
    new_enrichment_hash = enrichment_hash(new_extra)
    previous_core = None
    previous_enrich = None
    if previous is not None:
        old, old_extra = previous[:2]
        verify_manifest(old)
        # Both production readers supply core JSON. Two-item callers retain the
        # older comparison API for pure decision tests that do not read snapshots.
        if len(previous) >= 3:
            assert_additive_records(previous[2], {name: read_json(directory / name) for name in CORE})
        previous_core = all(old['fileSha256'][name] == current['fileSha256'][name]
                            for name in CORE)
        previous_enrich = enrichment_hash(old_extra) == new_enrichment_hash
        # A broken upstream parse must not silently wipe previously published data.
        old_candidates = int(old.get('counts', {}).get('benefitCandidates', 0))
        new_candidates = current.get('counts', {}).get('benefitCandidates', 0)
        if old_candidates >= 10 and new_candidates < old_candidates * 0.60:
            raise ValueError('Benefit candidates dropped >40%; manual review required')
        # Guard future changes when new official source adapters are introduced.
        for key in ('cards', 'merchants', 'catalogCardMerchantLinks'):
            prior = int(old.get('counts', {}).get(key, 0))
            after = int(current.get('counts', {}).get(key, 0))
            if prior >= 10 and after < prior * 0.90:
                raise ValueError(f'{key} dropped >10%; manual review required')
        core_version = old['dataVersion'] if previous_core else version_after(old['dataVersion'], proposed_version)
        old_extra_version = old.get('enrichmentVersion', 0)
        if type(old_extra_version) is not int or old_extra_version < 0:
            raise ValueError('Previous enrichmentVersion is invalid')
        extra_version = old_extra_version if previous_enrich else version_after(old_extra_version, proposed_version)
    else:
        core_version = proposed_version
        extra_version = proposed_version if any(new_extra[name] for name in ENRICHMENTS) else 0

    # One-time manifest schema extension is worth publishing, but must not
    # bump Android's dataVersion when the three core JSON files are identical.
    metadata_upgrade = previous is not None and (
        'enrichmentVersion' not in previous[0] or 'enrichmentSha256' not in previous[0])
    changed = previous is None or not (previous_core and previous_enrich) or metadata_upgrade
    current['dataVersion'] = core_version
    current['enrichmentVersion'] = extra_version
    current['enrichmentSha256'] = new_enrichment_hash
    # generatedAt is updated only if the artifact is actually deployed.
    if changed:
        current['generatedAt'] = now.isoformat()
    elif previous is not None:
        current['generatedAt'] = previous[0].get('generatedAt', current['generatedAt'])
    with closing(sqlite3.connect(directory / 'catalog.db')) as db:
        db.execute('UPDATE catalog_meta SET data_version=? WHERE singleton=1', (core_version,))
        if db.total_changes != 1:
            raise ValueError('catalog_meta row missing')
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite foreign key check failed')
    current['catalogSha256'] = hashlib.sha256((directory / 'catalog.db').read_bytes()).hexdigest()
    (directory / 'manifest.json').write_text(
        json.dumps(current, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return {'changed': changed, 'coreChanged': previous is None or not previous_core,
            'enrichmentChanged': previous is None or not previous_enrich,
            'dataVersion': core_version, 'enrichmentVersion': extra_version,
            'counts': current['counts']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='dist/v3')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--previous-url', help='Deployed v3 base URL (HTTPS)')
    group.add_argument('--previous-dir', help='Offline prior v3 directory')
    args = parser.parse_args()
    previous = (previous_from_url(args.previous_url) if args.previous_url
                else previous_from_dir(args.previous_dir))
    decision = publication_decision(args.out, previous)
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True, indent=2))
    output_path = os.environ.get('GITHUB_OUTPUT')
    if output_path:
        with open(output_path, 'a', encoding='utf-8') as out:
            out.write(f"changed={'true' if decision['changed'] else 'false'}\n")
            out.write(f"core_changed={'true' if decision['coreChanged'] else 'false'}\n")


if __name__ == '__main__':
    main()
