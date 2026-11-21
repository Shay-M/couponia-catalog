"""Issuer-reviewed factual associations for Couponia.

Never scrape issuer sites here. Each source is a short, manually reviewed
subset (not a bulk copied database), and every link remains 'listed', not
'confirmed at checkout'. Ambiguities fail closed.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import urlparse

from src.identity import normalize, merchant_names

CARD_ID = re.compile(r'^[a-z0-9][a-z0-9-]{2,70}$')
MAX_CARDS = 100
MAX_MERCHANTS_PER_CARD = 100
MAX_EXISTING_CARD_REVIEWS = 80
ALLOWED_CHANNELS = {'unknown', 'in_store', 'online', 'both'}
ALLOWED_SCOPES = {'network', 'selected_branches', 'venue', 'online'}


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
    matches = merchant_names(db).get(normalize(name), set())
    if len(matches) > 1:
        raise ValueError(f'Ambiguous merchant identity requires explicit review: {name}')
    return next(iter(matches), None)


def observation(value):
    observed = text(value, 'observedAt', 40)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', observed):
        raise ValueError('observedAt must be a UTC ISO timestamp')
    # A regex alone accepts impossible dates and times such as February 31.
    datetime.fromisoformat(observed.replace('Z', '+00:00'))
    return observed


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
    date.fromisoformat(payload['reviewedAt'])
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
        observed = observation(card.get('observedAt'))
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
            # Optional issuer-specific limitation for individual listed networks.
            # Keep the default caution for every association; never infer a
            # guaranteed purchase or online redemption from a logo listing.
            extra_note = item.get('restrictionNote') if isinstance(item, dict) else None
            if extra_note is not None:
                extra_note = text(extra_note, 'restrictionNote', 350)
            scope = item.get('listingScope', 'network') if isinstance(item, dict) else 'network'
            channel = item.get('redemptionChannel', 'unknown') if isinstance(item, dict) else 'unknown'
            if scope not in ALLOWED_SCOPES or channel not in ALLOWED_CHANNELS:
                raise ValueError('Invalid listingScope or redemptionChannel')
            limitation = 'Issuer list is partial and may change; check current terms.'
            if extra_note:
                limitation += ' ' + extra_note
            mid = get_or_create_merchant(db, listed_name, match)
            if mid in seen_merchants:
                raise ValueError(f'Duplicate merchant for {card_id}: {listed_name}')
            seen_merchants.add(mid)
            db.execute('''INSERT INTO card_merchants
                (card_id,merchant_id,source_id,listed_name,listing_scope,redemption_channel,
                 status,observed_at,restriction_note) VALUES (?,?,?,?,?,?,?,?,?)''',
                (card_id, mid, source_id, text(listed_name, 'listedName', 120), scope,
                 channel, 'listed', observed, limitation))
            link_count += 1
    additions = import_curated_existing_cards(db, payload)
    product_reviews = import_product_reviews(db, payload)
    return {'cards': len(seen_cards), 'links': link_count,
            'existingLinks': additions['added'], 'skippedExisting': additions['skipped'],
            'productReviews': product_reviews}


def import_curated_existing_cards(db, payload):
    """Add a small, product-scoped issuer-reviewed sample to seed cards.

    No implicit card creation, no fuzzy matching, no changing or deleting an
    existing card-merchant relationship. This is not a whole directory scraper.
    """
    entries = payload.get('existingCards', [])
    if not isinstance(entries, list) or len(entries) > MAX_EXISTING_CARD_REVIEWS:
        raise ValueError('Invalid existingCards list')
    seen_cards = set()
    added = skipped = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Existing card evidence must be an object')
        cid = text(entry.get('cardId'), 'existing card id', 80)
        if not CARD_ID.fullmatch(cid) or cid in seen_cards:
            raise ValueError(f'Duplicate or invalid existing card id: {cid}')
        seen_cards.add(cid)
        found = db.execute('SELECT name,issuer FROM cards WHERE id=?', (cid,)).fetchone()
        if found is None:
            raise ValueError(f'Unknown existing card id: {cid}')
        if found != (text(entry.get('expectedName'), 'expectedName', 150),
                     text(entry.get('issuer'), 'issuer', 120)):
            raise ValueError(f'Issuer/name mismatch for existing card: {cid}')
        source = issuer_url(entry.get('sourceUrl'))
        observed = observation(entry.get('observedAt'))
        source_id = text(entry.get('sourceId'), 'sourceId', 100)
        if not CARD_ID.fullmatch(source_id):
            raise ValueError('Invalid evidence sourceId')
        merchants = entry.get('merchants')
        if not isinstance(merchants, list) or not merchants or len(merchants) > MAX_MERCHANTS_PER_CARD:
            raise ValueError('Existing card needs a nonempty, limited issuer-listed sample')
        if found[1] == 'BUYME' and urlparse(source).hostname != 'buyme.co.il':
            raise ValueError('BUYME acceptance needs evidence from its actual issuer domain')
        if db.execute('SELECT 1 FROM sources WHERE id=?', (source_id,)).fetchone():
            raise ValueError(f'Source ID already exists: {source_id}')
        db.execute('INSERT INTO sources (id,url,evidence_level,captured_at,notes) VALUES (?,?,?,?,?)',
                   (source_id, source, 'issuer_list', observed,
                    'Limited manually reviewed source facts for one existing product.'))
        seen_merchants = set()
        for item in merchants:
            if isinstance(item, str):
                listed, approved = item, None
                restriction = None
                channel, scope = 'unknown', 'network'
            elif isinstance(item, dict):
                listed = item.get('name')
                approved = item.get('existingName')
                restriction = item.get('restrictionNote')
                channel = item.get('redemptionChannel', 'unknown')
                scope = item.get('listingScope', 'network')
            else:
                raise ValueError('Merchant must be a string or object')
            if restriction is not None:
                restriction = text(restriction, 'restrictionNote', 350)
            if scope not in ALLOWED_SCOPES or channel not in ALLOWED_CHANNELS:
                raise ValueError('Invalid listingScope or redemptionChannel')
            mid = get_or_create_merchant(db, listed, approved)
            if mid in seen_merchants:
                raise ValueError(f'Duplicate merchant for existing card {cid}: {listed}')
            seen_merchants.add(mid)
            if db.execute('SELECT 1 FROM card_merchants WHERE card_id=? AND merchant_id=?',
                          (cid, mid)).fetchone():
                skipped += 1
                continue
            note = 'Issuer list is partial and may change; check current terms.'
            if restriction:
                note += ' ' + restriction
            db.execute('''INSERT INTO card_merchants
                (card_id,merchant_id,source_id,listed_name,listing_scope,redemption_channel,
                 status,observed_at,restriction_note) VALUES (?,?,?,?,?,?,?,?,?)''',
                (cid, mid, source_id, text(listed, 'listedName', 120), scope,
                 channel, 'listed', observed, note))
            added += 1
        # Replace generic category landing URLs with reviewed product-specific issuer URLs.
        if entry.get('updateSourceUrl') is True:
            db.execute('UPDATE cards SET source_url=? WHERE id=?', (source, cid))
    return {'added': added, 'skipped': skipped}


def import_product_reviews(db, payload):
    """Update only a seed card's product URL, never fabricate merchant links."""
    entries = payload.get('productReviews', [])
    if not isinstance(entries, list) or len(entries) > MAX_EXISTING_CARD_REVIEWS:
        raise ValueError('Invalid productReviews list')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('productReviews must contain objects')
        cid = text(entry.get('cardId'), 'cardId', 80)
        if not CARD_ID.fullmatch(cid) or cid in seen:
            raise ValueError(f'Duplicate/invalid product-only cardId: {cid}')
        seen.add(cid)
        found = db.execute('SELECT name,issuer,notes FROM cards WHERE id=?', (cid,)).fetchone()
        if found is None or found[:2] != (text(entry.get('expectedName'), 'expectedName', 150),
                                           text(entry.get('issuer'), 'issuer', 120)):
            raise ValueError(f'Unknown or mismatched product-only card: {cid}')
        observed = observation(entry.get('observedAt'))
        source = issuer_url(entry.get('sourceUrl'))
        sid = text(entry.get('sourceId'), 'sourceId', 100)
        if not CARD_ID.fullmatch(sid) or db.execute('SELECT 1 FROM sources WHERE id=?', (sid,)).fetchone():
            raise ValueError(f'Duplicate or invalid product-only source id: {sid}')
        note = text(entry.get('note'), 'product note', 500)
        if entry.get('merchants') not in (None, []):
            raise ValueError('productReviews may not contain merchant associations')
        db.execute('INSERT INTO sources (id,url,evidence_level,captured_at,notes) VALUES (?,?,?,?,?)',
                   (sid, source, 'issuer_product', observed, 'Product URL and terms only; no merchant evidence.'))
        db.execute('UPDATE cards SET source_url=?,notes=? WHERE id=?',
                   (source, (found[2] + ' ' + note).strip(), cid))
    return len(seen)
