"""Issuer-reviewed factual associations for Couponia.

Never scrape issuer sites here. Each source is a short, manually reviewed
subset (not a bulk copied database), and every link remains 'listed', not
'confirmed at checkout'. Ambiguities fail closed.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from src.identity import normalize, match_names

CARD_ID = re.compile(r'^[a-z0-9][a-z0-9-]{2,70}$')
MAX_CARDS = 100
MAX_MERCHANTS_PER_CARD = 100


def text(value, label, max_length=180):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f'{label}: missing or invalid text')
    return value.strip()


def issuer_url(value):
    url = text(value, 'sourceUrl', 512)
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
            parsed.password or parsed.port or parsed.fragment or
            parsed.hostname in ('localhost', '127.0.0.1')):
        raise ValueError('Issuer evidence must be a public HTTPS URL')
    return url


def lookup_existing_merchant(db, name):
    index = match_names(db)
    return index.get(normalize(name))


def get_or_create_merchant(db, listed_name, existing_name=None):
    name = text(listed_name, 'merchant name', 120)
    reference = text(existing_name, 'existingName', 120) if existing_name else name
    found = lookup_existing_merchant(db, reference)
    if existing_name and found is None:
        raise ValueError(f'Unknown approved existing merchant name: {reference}')
    if found:
        mid = found
    else:
        key = normalize(name)
        if not key:
            raise ValueError('Empty normalized merchant name')
        mid = 'm_' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]
        row = db.execute('SELECT normalized_name FROM merchants WHERE id=?', (mid,)).fetchone()
        if row and normalize(row[0]) != key:
            raise ValueError(f'Merchant id collision: {name}')
        db.execute('INSERT OR IGNORE INTO merchants (id,name,normalized_name) VALUES (?,?,?)',
                   (mid, name, key))
    # Preserve the source spelling as a searchable alias without changing canonical names.
    existing = db.execute('SELECT merchant_id FROM merchant_aliases WHERE alias=?', (name,)).fetchone()
    if existing and existing[0] != mid:
        raise ValueError(f'Merchant alias conflicts with an existing brand: {name}')
    if not existing:
        db.execute('INSERT INTO merchant_aliases (alias,merchant_id) VALUES (?,?)', (name, mid))
    return mid


def import_curated_issuers(db, payload):
    if not isinstance(payload, dict) or payload.get('schemaVersion') != 1:
        raise ValueError('Issuer curation must have schemaVersion=1')
    cards = payload.get('cards')
    if not isinstance(cards, list) or len(cards) == 0 or len(cards) > MAX_CARDS:
        raise ValueError('Invalid issuer curation cards')
    if not isinstance(payload.get('reviewedAt'), str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', payload['reviewedAt']):
        raise ValueError('reviewedAt must be YYYY-MM-DD')
    seen_cards = set()
    link_count = 0
    for card in cards:
        if not isinstance(card, dict):
            raise ValueError('Card must be an object')
        card_id = text(card.get('id'), 'card id')
        if not CARD_ID.fullmatch(card_id) or card_id in seen_cards:
            raise ValueError(f'Duplicate or invalid card id: {card_id}')
        seen_cards.add(card_id)
        if db.execute('SELECT 1 FROM cards WHERE id=?', (card_id,)).fetchone():
            raise ValueError(f'Curated card collides with existing catalog: {card_id}')
        source_id = text(card.get('sourceId'), 'sourceId', 100)
        source = issuer_url(card.get('sourceUrl'))
        observed = text(card.get('observedAt'), 'observedAt', 40)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', observed):
            raise ValueError('observedAt must be a UTC ISO timestamp')
        name = text(card.get('name'), 'card name', 150)
        issuer = text(card.get('issuer'), 'issuer', 120)
        note = text(card.get('notes'), 'notes', 600)
        merchants = card.get('merchants')
        if not isinstance(merchants, list) or len(merchants) > MAX_MERCHANTS_PER_CARD:
            raise ValueError('Invalid merchant list')
        # Sources are IDs scoped to exactly one issuer product page.
        if db.execute('SELECT 1 FROM sources WHERE id=?', (source_id,)).fetchone():
            raise ValueError(f'Source ID already exists: {source_id}')
        db.execute('INSERT INTO sources (id,url,evidence_level,captured_at,notes) VALUES (?,?,?,?,?)',
                   (source_id, source, 'issuer_list' if merchants else 'issuer_product',
                    observed, 'Manually reviewed limited factual subset; not a live or complete listing.'))
        db.execute('INSERT INTO cards (id,name,issuer,coverage,source_url,updated_at,notes) VALUES (?,?,?,?,?,?,?)',
                   (card_id, name, issuer, 'partial', source, observed, note))
        db.execute('INSERT INTO card_details (card_id,card_type,merchant_scope,publication_state,notes) VALUES (?,?,?,?,?)',
                   (card_id, 'multi_merchant', 'multiple_stores', 'confirmed_public_product',
                    'A partial issuer page listing or product-only evidence; never infer absent stores are rejected.'))
        seen_merchants = set()
        for item in merchants:
            if isinstance(item, str):
                listed_name, match = item, None
            elif isinstance(item, dict):
                listed_name, match = item.get('name'), item.get('existingName')
            else:
                raise ValueError('Merchant must be string or name/existingName object')
            mid = get_or_create_merchant(db, listed_name, match)
            if mid in seen_merchants:
                raise ValueError(f'Duplicate merchant for {card_id}: {listed_name}')
            seen_merchants.add(mid)
            db.execute('''INSERT INTO card_merchants
                (card_id,merchant_id,source_id,listed_name,listing_scope,redemption_channel,
                 status,observed_at,restriction_note) VALUES (?,?,?,?,?,?,?,?,?)''',
                (card_id, mid, source_id, text(listed_name, 'listedName', 120), 'network',
                 'unknown', 'listed', observed, 'Issuer list is partial and may change; check current terms.'))
            link_count += 1
    return {'cards': len(seen_cards), 'links': link_count}
