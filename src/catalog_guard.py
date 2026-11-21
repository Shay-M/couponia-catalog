"""Read-only protection against a silently truncated Couponia catalog.

Checks immutable baseline entries and, optionally, the last published local
SQLite snapshot. Does not assume a missing issuer link means rejection.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3


class SnapshotRegression(ValueError):
    pass


def _snapshot(path):
    path = Path(path)
    if not path.is_file():
        raise SnapshotRegression(f'Missing snapshot: {path}')
    with closing(sqlite3.connect(f'file:{path.resolve().as_posix()}?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise SnapshotRegression(f'Integrity failed: {path}')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise SnapshotRegression(f'Foreign keys failed: {path}')
        cards = {row[0]: row[1:] for row in db.execute('SELECT id,name,issuer FROM cards')}
        merchants = {row[0]: row[1] for row in db.execute('SELECT id,name FROM merchants')}
        # A relationship cannot change issuer evidence without explicit review.
        links = {(r[0],r[1]): r[2:] for r in db.execute(
            'SELECT card_id,merchant_id,source_id,status,listing_scope,redemption_channel FROM card_merchants')}
    return cards, merchants, links


def _short_ids(items, limit=6):
    vals = sorted(map(str, items))
    return ', '.join(vals[:limit]) + (f' and {len(vals)-limit} more' if len(vals)>limit else '')


def assert_additive(reference_path, candidate_path):
    """Fail closed on deleted or silently remapped known facts."""
    return _assert_additive(_snapshot(reference_path), _snapshot(candidate_path))


def assert_additive_records(reference, candidate):
    """The same identity guard for hash-verified published JSON snapshots.

    A real issuer withdrawal requires a reviewed baseline adjustment; this gate
    detects accidental losses and is not a claim that acceptance never changes.
    """
    def snapshot(files):
        cards = {r['id']: (r['name'], r['issuer']) for r in files['cards.json']}
        merchants = {r['id']: r['name'] for r in files['merchants.json']}
        links = {(r['card_id'], r['merchant_id']):
                 (r['source_id'], r['status'], r['listing_scope'], r['redemption_channel'])
                 for r in files['acceptance.json']}
        for filename, index in (('cards.json',cards),('merchants.json',merchants),('acceptance.json',links)):
            if len(index) != len(files[filename]):
                raise SnapshotRegression(f'Duplicate identities in {filename}')
        return cards, merchants, links
    return _assert_additive(snapshot(reference), snapshot(candidate))


def _assert_additive(before_snapshot, after_snapshot):
    ref_cards, ref_merchants, ref_links = before_snapshot
    new_cards, new_merchants, new_links = after_snapshot
    for name, before, after in (
        ('cards', ref_cards, new_cards),
        ('merchants', ref_merchants, new_merchants),
        ('card-merchants', ref_links, new_links),
    ):
        lost = before.keys() - after.keys()
        if lost:
            raise SnapshotRegression(f'Unexpected deleted {name}: {_short_ids(lost)}')
        changed = {key for key in before.keys() if before[key] != after[key]}
        if changed:
            raise SnapshotRegression(f'Unexpected changed {name} identities: {_short_ids(changed)}')
    return {
        'cardsAdded': len(new_cards)-len(ref_cards),
        'merchantsAdded': len(new_merchants)-len(ref_merchants),
        'linksAdded': len(new_links)-len(ref_links),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', default='seed/catalog-v2.db')
    parser.add_argument('--catalog', default='dist/v3/catalog.db')
    parser.add_argument('--previous-db', help='Optional previously published snapshot downloaded by operator')
    args = parser.parse_args()
    print('Immutable baseline audit:',assert_additive(args.seed,args.catalog))
    if args.previous_db:
        print('Previous release comparison:', assert_additive(args.previous_db,args.catalog))
    print('Catalog guard passed; no existing card, merchant or acceptance links lost.')


if __name__=='__main__':
    main()
