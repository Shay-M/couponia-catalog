"""Explicit voucher purchase -> exact product -> exact merchant evidence.

No parent-chain/name inference and no selected-branch guessing. This module
knows no network or UI concerns; the publisher supplies a validated catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from src.offer_contract import _nonempty
from src.offer_sources import MEMBERSHIPS, official_domain

MAX_AMOUNT_MINOR = 1_000_000_000_000
PURCHASE_FIELDS = (
    'voucherCardId', 'merchantIds', 'redemptionChannel', 'membershipIds',
    'faceValueMinor', 'priceMinor', 'currency', 'purchaseUrl', 'conditionsSummary',
)


def _id(value):
    return _nonempty(value, 160) and not any(ord(c) < 32 for c in value)


def _ids(value, limit):
    return (isinstance(value, list) and 1 <= len(value) <= limit
            and all(_id(item) for item in value) and len(set(value)) == len(value))


def compatible_channel(requested, recorded):
    return recorded == requested or (requested in {'in_store', 'online'} and recorded == 'both')


def compatible_scope(requested, scope):
    return scope in {'network', 'venue', 'single_brand_only'} or (requested == 'online' and scope == 'online')


@dataclass(frozen=True)
class CatalogEvidence:
    cards: frozenset[str]
    merchants: frozenset[str]
    # Key is (voucher product, exact merchant); value is (status, scope, channel).
    acceptance: dict[tuple[str, str], tuple[str, str, str]]

    @classmethod
    def from_directory(cls, directory):
        """Read the same content-hashed v3 snapshot consumed by Android."""
        directory = Path(directory)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('schemaVersion') != 3:
            raise ValueError('Purchase evidence requires catalog schema 3')
        rows = {}
        for filename, count_key in (
                ('cards.json', 'cards'), ('merchants.json', 'merchants'),
                ('acceptance.json', 'catalogCardMerchantLinks')):
            path = directory / filename
            if path.stat().st_size > 10_000_000:
                raise ValueError('Catalog evidence file too large')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest['fileSha256'][filename]:
                raise ValueError('Catalog evidence checksum mismatch')
            data = json.loads(raw)
            if (not isinstance(data, list) or not all(isinstance(row, dict) for row in data)
                    or type(manifest['counts'][count_key]) is not int
                    or len(data) != manifest['counts'][count_key]):
                raise ValueError('Invalid catalog evidence collection')
            rows[filename] = data
        cards = [row['id'] for row in rows['cards.json']]
        merchants = [row['id'] for row in rows['merchants.json']]
        if (not all(_id(item) for item in cards + merchants)
                or len(set(cards)) != len(cards) or len(set(merchants)) != len(merchants)):
            raise ValueError('Duplicate or invalid catalog IDs')
        links = {}
        for row in rows['acceptance.json']:
            key = (row['card_id'], row['merchant_id'])
            if key in links or key[0] not in cards or key[1] not in merchants:
                raise ValueError('Invalid catalog acceptance reference')
            links[key] = (row['status'], row['listing_scope'], row['redemption_channel'])
        return cls(frozenset(cards), frozenset(merchants), links)

    def supports(self, purchase):
        card = purchase['voucherCardId']
        channel = purchase['redemptionChannel']
        if card not in self.cards:
            return False
        for merchant in purchase['merchantIds']:
            edge = self.acceptance.get((card, merchant))
            if (merchant not in self.merchants or edge is None or edge[0] != 'listed'
                    or not compatible_scope(channel, edge[1])
                    or not compatible_channel(channel, edge[2])):
                return False
        return True


def purchase_reasons(offer, catalog):
    if 'purchase' not in offer:
        return []
    p = offer['purchase']
    if not isinstance(p, dict):
        return ['invalid_purchase_shape']
    reasons = []
    if offer.get('offerType') != 'voucher_discount':
        reasons.append('purchase_requires_voucher_discount')
    if not _id(p.get('voucherCardId')) or not _ids(p.get('merchantIds'), 100):
        reasons.append('invalid_purchase_catalog_ids')
    if p.get('redemptionChannel') not in ('in_store', 'online', 'both'):
        reasons.append('invalid_purchase_channel')
    members = p.get('membershipIds')
    if (not _ids(members, 20)
            or any(MEMBERSHIPS.get(mid) != offer.get('sourceId') for mid in members)):
        reasons.append('invalid_purchase_memberships')
    face, price = p.get('faceValueMinor'), p.get('priceMinor')
    if (type(face) is not int or type(price) is not int
            or not 1 <= price < face <= MAX_AMOUNT_MINOR):
        reasons.append('invalid_purchase_amounts')
    if p.get('currency') != 'ILS':
        reasons.append('invalid_purchase_currency')
    if not official_domain(offer.get('sourceId'), p.get('purchaseUrl')):
        reasons.append('non_issuer_purchase_url')
    conditions = p.get('conditionsSummary')
    if not _nonempty(conditions, 500):
        reasons.append('missing_purchase_conditions')
    if not reasons:
        if catalog is None:
            reasons.append('purchase_catalog_evidence_missing')
        elif not catalog.supports(p):
            reasons.append('purchase_catalog_evidence_mismatch')
    return reasons
