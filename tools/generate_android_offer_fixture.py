"""Generate Android contract-test resources using the real Python publisher.

Everything created here is synthetic test data, including the grant. Never copy
the output to dist/ or config/approved_offers.json. No network request is made.

Run from the catalog root:
  python tools/generate_android_offer_fixture.py --out <Android test-resource directory>
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.publish_offers import build

NOW = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def stamp(value):
    return value.isoformat().replace('+00:00', 'Z')


def generate(out):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        catalog = root / 'catalog'
        catalog.mkdir()
        files = {
            'cards.json': [{'id': 'fixture-voucher'}],
            'merchants.json': [{'id': 'fixture-store'}],
            'acceptance.json': [{
                'card_id': 'fixture-voucher', 'merchant_id': 'fixture-store',
                'status': 'listed', 'listing_scope': 'network', 'redemption_channel': 'in_store',
            }],
        }
        hashes = {}
        for name, data in files.items():
            write(catalog / name, data)
            hashes[name] = hashlib.sha256((catalog / name).read_bytes()).hexdigest()
        write(catalog / 'manifest.json', {
            'schemaVersion': 3, 'counts': {'cards': 1, 'merchants': 1, 'catalogCardMerchantLinks': 1},
            'fileSha256': hashes,
        })
        write(root / 'offers-input.json', {'schemaVersion': 1, 'offers': [{
            'offerId': 'fixture-offer-not-for-publication', 'sourceId': 'hot-club',
            'issuerProductId': 'fixture-hot-product', 'merchantName': 'SYNTHETIC TEST STORE',
            'titleHe': 'נתוני בדיקה בלבד — לא הצעה אמיתית',
            'titleEn': 'SYNTHETIC TEST ONLY — not a real offer',
            'eligibilitySummary': 'Synthetic HOT Visa declaration for tests only.',
            'termsSummary': 'Do not purchase or publish. This fixture only verifies the contract.',
            'offerType': 'voucher_discount',
            'issuerEvidenceUrl': 'https://www.hot.co.il/test-only-not-a-real-offer',
            'rightsBasis': 'owned_data', 'verificationStatus': 'issuer_verified', 'stockStatus': 'available',
            'checkedAt': stamp(NOW - timedelta(hours=1)),
            'validFrom': stamp(NOW - timedelta(days=1)), 'validUntil': stamp(NOW + timedelta(days=2)),
            'purchase': {
                'voucherCardId': 'fixture-voucher', 'merchantIds': ['fixture-store'],
                'redemptionChannel': 'in_store', 'membershipIds': ['hot-visa'],
                'faceValueMinor': 10_000, 'priceMinor': 9_000, 'currency': 'ILS',
                'purchaseUrl': 'https://www.hot.co.il/test-only-not-a-real-offer',
                'conditionsSummary': 'Synthetic test fixture. Not an offer. Do not publish.',
            },
        }]})
        write(root / 'grants.json', {'schemaVersion': 1, 'grants': [{
            'sourceId': 'hot-club', 'approvedForRedistribution': True, 'rightsBasis': 'owned_data',
            'grantReference': 'SYNTHETIC TEST DATA OWNED BY TEST',
            'validUntil': stamp(NOW + timedelta(hours=2)),
        }]})
        write(root / 'registry.json', {'schemaVersion': 1, 'sources': [{'id': 'hot-club', 'enabled': True}]})
        report = build(root/'offers-input.json', root/'grants.json', root/'registry.json',
                       out, now=NOW, catalog_dir=catalog)
        if report['published'] != 1 or report['excluded'] != 0:
            raise AssertionError(f'Fixture must exercise a positive publication: {report}')
        print(json.dumps({'testDataOnly': True, **report}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    generate(parser.parse_args().out)
