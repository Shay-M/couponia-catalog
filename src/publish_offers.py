"""Publish reviewed benefit offers to the independent offers/v1 feed.

Orchestration only: field/time rules, issuer policy and exact purchase evidence
are separate modules. A disabled source or an absent/expired grant cannot publish.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.offer_contract import ALLOWED_RIGHTS, STRING_LIMITS, _utc, check_offer_publication
from src.offer_sources import SOURCE_DOMAINS, official_domain
from src.purchase_contract import CatalogEvidence, PURCHASE_FIELDS, purchase_reasons

SCHEMA = 1
MAX_OFFERS = 400
MAX_FILE = 300_000
FIELDS = tuple(STRING_LIMITS)


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def check_grants(grants, now):
    if (not isinstance(grants, dict) or type(grants.get('schemaVersion')) is not int
            or grants['schemaVersion'] != SCHEMA or not isinstance(grants.get('grants'), list)):
        raise ValueError('Invalid permission-grants schema')
    approved, seen = {}, set()
    for g in grants['grants']:
        if not isinstance(g, dict):
            raise ValueError('Invalid permission grant')
        source_id = g.get('sourceId')
        if not isinstance(source_id, str) or source_id not in SOURCE_DOMAINS or source_id in seen:
            raise ValueError('Unknown/duplicate grant source')
        seen.add(source_id)
        if (g.get('approvedForRedistribution') is not True
                or not isinstance(g.get('rightsBasis'), str) or g['rightsBasis'] not in ALLOWED_RIGHTS
                or not isinstance(g.get('grantReference'), str)
                or not 8 <= len(g['grantReference'].strip()) <= 2000):
            raise ValueError('Permission grant requires documented affirmative authorization')
        try:
            expiry = _utc(g.get('validUntil'))
        except (TypeError, ValueError) as e:
            raise ValueError('Permission grant requires UTC expiry') from e
        if expiry > now:
            approved[source_id] = (g['rightsBasis'], expiry)
    return approved


def enabled_sources(registry):
    if (not isinstance(registry, dict) or type(registry.get('schemaVersion')) is not int
            or registry['schemaVersion'] != SCHEMA or not isinstance(registry.get('sources'), list)):
        raise ValueError('Invalid offer-source registry')
    sources = {}
    for source in registry['sources']:
        if not isinstance(source, dict):
            raise ValueError('Invalid offer-source entry')
        sid = source.get('id')
        if (not isinstance(sid, str) or sid not in SOURCE_DOMAINS or sid in sources
                or type(source.get('enabled')) is not bool):
            raise ValueError('Unknown/duplicate source or invalid enabled flag')
        sources[sid] = source['enabled']
    return sources


def build(approved_file: Path, grants_file: Path, registry_file: Path, out: Path,
          now=None, catalog_dir: Path | None = None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Publication clock must be timezone aware')
    payload = load(approved_file)
    if (not isinstance(payload, dict) or type(payload.get('schemaVersion')) is not int
            or payload['schemaVersion'] != SCHEMA or not isinstance(payload.get('offers'), list)):
        raise ValueError('Invalid approved offers input')
    if len(payload['offers']) > MAX_OFFERS:
        raise ValueError('Too many offers')
    sources = enabled_sources(load(registry_file))
    grants = check_grants(load(grants_file), now)
    # Empty/generic feeds do not depend on catalog loading. Purchase records do.
    needs_catalog = any(isinstance(o, dict) and 'purchase' in o for o in payload['offers'])
    catalog = CatalogEvidence.from_directory(catalog_dir) if needs_catalog and catalog_dir is not None else None
    seen, active, excluded = set(), [], Counter()
    for offer in payload['offers']:
        if not isinstance(offer, dict):
            raise ValueError('Offer must be an object')
        oid = offer.get('offerId')
        if (not isinstance(oid, str) or not oid.strip() or oid != oid.strip()
                or len(oid) > 160 or oid in seen):
            raise ValueError('Invalid/duplicate offer ID')
        seen.add(oid)
        source = offer.get('sourceId')
        reasons = list(check_offer_publication(offer, now)['reasons'])
        if not isinstance(source, str) or source not in sources:
            reasons.append('unknown_offer_provider')
            grant = None
        else:
            if not sources[source]:
                reasons.append('source_disabled')
            grant = grants.get(source)
        if grant is None or grant[0] != offer.get('rightsBasis'):
            reasons.append('no_active_explicit_source_permission')
        if not official_domain(source, offer.get('issuerEvidenceUrl')):
            reasons.append('non_issuer_domain')
        reasons.extend(purchase_reasons(offer, catalog))
        if reasons:
            excluded.update(set(reasons))
            continue
        # Publish allowlisted data only; reviewer notes and grantReference remain private.
        row = {key: offer[key] for key in FIELDS}
        # A device may retain this feed. It must stop showing the offer no later
        # than the source grant's expiry, even before another scheduled build.
        expiry = min(_utc(offer['validUntil']), grant[1])
        row['validUntil'] = expiry.isoformat().replace('+00:00', 'Z')
        if 'purchase' in offer:
            row['purchase'] = {key: offer['purchase'][key] for key in PURCHASE_FIELDS}
        active.append(row)
    active.sort(key=lambda row: (row['sourceId'], row['merchantName'], row['offerId']))
    serialized = (json.dumps(active, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    if len(serialized) > MAX_FILE:
        raise ValueError('Offers feed too large')
    sha = hashlib.sha256(serialized).hexdigest()
    manifest = {
        'schemaVersion': SCHEMA,
        'generatedAt': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'fileSha256': {'offers.json': sha},
        'counts': {'offers': len(active)},
    }
    out.mkdir(parents=True, exist_ok=True)
    # Consumers authenticate offers against the manifest; write the manifest last.
    # GitHub Pages publishes the completed directory as one deployment artifact.
    (out / 'offers.json').write_bytes(serialized)
    (out / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'published': len(active), 'excluded': len(payload['offers']) - len(active),
            'exclusionReasons': dict(sorted(excluded.items())), 'sha256': sha}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approved-file', default='config/approved_offers.json')
    parser.add_argument('--rights-file', default='config/offer_rights_grants.json')
    parser.add_argument('--registry-file', default='config/offer_source_registry.json')
    parser.add_argument('--catalog-dir', default='dist/v3', help='Validated v3 snapshot for purchase reference checks')
    parser.add_argument('--out', default='dist/offers/v1')
    args = parser.parse_args()
    report = build(Path(args.approved_file), Path(args.rights_file),
                   Path(args.registry_file), Path(args.out), catalog_dir=Path(args.catalog_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
