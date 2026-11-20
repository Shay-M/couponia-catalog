"""Extend the local v2 catalog with *unverified* external candidates.

Standard-library-only. The output is an additive SQLite schema v3, intended
for a repository's GitHub Pages deployment, not a ready-made Room migration.
"""
import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
import re
import shutil
import sqlite3
import unicodedata
from urllib.request import Request, urlopen

CLAW_REPO = 'https://github.com/yhyatt/ClawSavings'
BUYME_REPO = 'https://github.com/eladkishon/buyme-mcp'


def normalize(value):
    s = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ' '.join(re.sub(r'[^\w\u0590-\u05ff]+', ' ', s).split())


def checksum(*values):
    return hashlib.sha256('|'.join(map(str, values)).encode('utf-8')).hexdigest()[:24]


def as_number(value):
    try:
        return float(value) if value is not None and value != '' and not isinstance(value, bool) else None
    except (ValueError, TypeError):
        return None


def as_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def read_remote_json(url):
    req = Request(url, headers={'User-Agent':'unified-gift-card-catalog/0.1','Accept':'application/json'})
    with urlopen(req, timeout=30) as response:
        raw = response.read(6_000_001)
    if len(raw) > 6_000_000:
        raise ValueError('Source too large')
    return json.loads(raw)


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS external_sources (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, source_url TEXT NOT NULL,
            license_note TEXT NOT NULL, imported_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS benefit_candidates (
            id TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES external_sources(id),
            merchant_name TEXT NOT NULL, matched_merchant_id TEXT REFERENCES merchants(id),
            category TEXT NOT NULL, benefit_type TEXT NOT NULL, face_value REAL,
            price REAL, points REAL, discount_pct REAL, observed_at TEXT,
            freshness TEXT NOT NULL, evidence_url TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'unverified');
        CREATE TABLE IF NOT EXISTS acceptance_candidates (
            origin TEXT NOT NULL, external_id TEXT NOT NULL, card_id TEXT NOT NULL,
            merchant_name TEXT NOT NULL, matched_merchant_id TEXT REFERENCES merchants(id),
            evidence_url TEXT NOT NULL, verification_status TEXT NOT NULL DEFAULT 'unverified',
            PRIMARY KEY (origin, external_id));
        CREATE INDEX IF NOT EXISTS idx_candidates_merchant ON benefit_candidates(matched_merchant_id);
    ''')


def match_names(db):
    aliases = {}
    for mid, name in db.execute('SELECT id,name FROM merchants'):
        aliases.setdefault(normalize(name), set()).add(mid)
    for alias, mid in db.execute('SELECT alias, merchant_id FROM merchant_aliases'):
        aliases.setdefault(normalize(alias), set()).add(mid)
    return {key: next(iter(ids)) for key, ids in aliases.items() if key and len(ids) == 1}


def import_clawsavings(db, payload, now):
    categories = payload.get('categories') if isinstance(payload, dict) else None
    if not isinstance(categories, dict) or not categories:
        raise ValueError('Unexpected ClawSavings JSON (no categories)')
    details = payload.get('discount_sources', payload.get('sources', {}))
    if not isinstance(details, dict):
        details = {}
    idx = match_names(db)
    count = 0
    for category, info in categories.items():
        if not isinstance(info, dict):
            continue
        for provider, source in info.get('sources', {}).items():
            if not isinstance(source, dict):
                continue
            fullid = 'clawsavings:' + provider
            desc = details.get(provider, {})
            if not isinstance(desc, dict):
                desc = {}
            url = desc.get('url') or source.get('source_url') or CLAW_REPO
            db.execute('INSERT OR IGNORE INTO external_sources VALUES (?,?,?,?,?)',
                (fullid, desc.get('name_he') or desc.get('name') or provider,
                 url, 'ClawSavings README declares MIT; provider rights not established', now.isoformat()))
            deals = source.get('deals') or []
            if not isinstance(deals, list):
                continue
            for item in deals:
                if not isinstance(item, dict) or not item.get('store'):
                    continue
                observed = as_date(item.get('cached_at') or source.get('cached_at') or source.get('verified_at'))
                delta = (now.date() - observed).days if observed else None
                freshness = 'unknown' if delta is None or delta < 0 else 'fresh' if delta <= 45 else 'stale'
                name = str(item['store']).strip()
                identity = checksum(fullid, category, name, item.get('description'), item.get('price'))
                evidence = item.get('webview_url') or item.get('url') or source.get('source_url') or source.get('voucher_url') or url
                db.execute('''INSERT OR REPLACE INTO benefit_candidates
                    (id,provider_id,merchant_name,matched_merchant_id,category,benefit_type,face_value,price,
                     points,discount_pct,observed_at,freshness,evidence_url,verification_status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (identity,fullid,name,idx.get(normalize(name)),category,source.get('type','voucher'),
                     as_number(item.get('face_value')),as_number(item.get('price')),
                     as_number(item.get('extra_points')),as_number(item.get('effective_pct')),
                     observed.isoformat() if observed else None,freshness,evidence,'unverified'))
                count += 1
    return count


def import_buyme_preview(db, payload, now, minimum=100):
    """Optional, permission-gated candidate import: NEVER marks a shop accepting."""
    if not isinstance(payload,dict) or payload.get('masterVoucherId') != 13438757:
        raise ValueError('Expected BUYME ALL scope 13438757')
    items = payload.get('businesses')
    if not isinstance(items,list) or len(items) < minimum:
        raise ValueError('BUYME snapshot unexpectedly small')
    if payload.get('businessCount') is not None and payload['businessCount'] != len(items):
        raise ValueError('BUYME businessCount mismatch')
    db.execute('INSERT OR REPLACE INTO external_sources VALUES (?,?,?,?,?)',
        ('buyme-mcp','BUYME MCP',BUYME_REPO,'No explicit license confirmed; do not redistribute without permission',now.isoformat()))
    idx = match_names(db)
    n=0
    for item in items:
        if not isinstance(item,dict) or not item.get('id') or not item.get('name'):
            continue
        name = str(item['name']).strip()
        db.execute('''INSERT OR REPLACE INTO acceptance_candidates
            (origin,external_id,card_id,merchant_name,matched_merchant_id,evidence_url,verification_status)
            VALUES(?,?,?,?,?,?,?)''',
            ('buyme-mcp',str(item['id']),'buyme-all',name,idx.get(normalize(name)),
             item.get('url') or 'https://buyme.co.il/supplier/'+str(item['id']), 'unverified'))
        n+=1
    return n


def dump_table(db, name):
    cursor = db.execute('SELECT * FROM ' + name + ' ORDER BY 1')
    keys = [x[0] for x in cursor.description]
    return [dict(zip(keys,row)) for row in cursor]


def json_write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def build(seed, output, claw=None, buyme=None, minimum=100, clock=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    now = clock or datetime.now(timezone.utc)
    stage = output/'.catalog.staging.db'
    if stage.exists(): stage.unlink()
    shutil.copyfile(seed, stage)
    n_claw=n_buyme=0
    try:
        with sqlite3.connect(stage) as db:
            db.execute('PRAGMA foreign_keys=ON')
            initialize(db)
            if claw is not None:
                n_claw=import_clawsavings(db, claw, now)
            if buyme is not None:
                n_buyme=import_buyme_preview(db, buyme, now, minimum)
            db.execute('UPDATE catalog_meta SET schema_version=3, data_version=?, captured_at=? WHERE singleton=1',
                (int(now.strftime('%Y%m%d%H%M%S')), now.isoformat()))
            db.execute('PRAGMA user_version=3')
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('SQLite integrity check failed')
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('SQLite foreign key check failed')
            cards = dump_table(db,'cards')
            merchants = dump_table(db,'merchants')
            relations = dump_table(db,'card_merchants')
            benefits = dump_table(db,'benefit_candidates')
            acceptance = dump_table(db,'acceptance_candidates')
            sources = dump_table(db,'external_sources')
            if min(len(cards),len(merchants),len(relations)) < 99:
                raise ValueError('Baseline truncated')
            if len(merchants)<409 or len(relations)<504:
                raise ValueError('v2 source records unexpectedly missing')
            db.commit()
        os.replace(stage, output/'catalog.db')
        json_write(output/'cards.json', cards)
        json_write(output/'merchants.json',merchants)
        json_write(output/'acceptance.json',relations)
        json_write(output/'benefit_candidates.json',benefits)
        json_write(output/'acceptance_candidates.json',acceptance)
        json_write(output/'sources.json',sources)
        manifest = {
            'schemaVersion':3, 'dataVersion':int(now.strftime('%Y%m%d%H%M%S')),
            'generatedAt':now.isoformat(),
            'counts':{'cards':len(cards),'merchants':len(merchants),
               'catalogCardMerchantLinks':len(relations),
               'benefitCandidates':len(benefits),
               'freshBenefitCandidates':sum(x['freshness']=='fresh' for x in benefits),
               'buymeAcceptanceCandidates':len(acceptance)},
            'imports':{'clawsavings':n_claw,'buymeOptional':n_buyme},
            'catalogSha256':hashlib.sha256((output/'catalog.db').read_bytes()).hexdigest(),
            'fileSha256':{filename:hashlib.sha256((output/filename).read_bytes()).hexdigest()
                for filename in ('cards.json','merchants.json','acceptance.json')},
            'warning':'Candidates are NOT confirmed checkout acceptance; missing links mean unknown.'}
        json_write(output/'manifest.json',manifest)
        return manifest
    finally:
        if stage.exists(): stage.unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed',default='seed/catalog-v2.db')
    p.add_argument('--out',default='dist/v3')
    p.add_argument('--clawsavings-url')
    p.add_argument('--clawsavings-file')
    p.add_argument('--buyme-file',help='Optional ONLY if upstream redistribution rights established')
    p.add_argument('--buyme-minimum',type=int,default=100)
    a=p.parse_args()
    if a.clawsavings_url and a.clawsavings_file:
        p.error('Select only one ClawSavings input')
    claw = read_remote_json(a.clawsavings_url) if a.clawsavings_url else json.loads(Path(a.clawsavings_file).read_text(encoding='utf8')) if a.clawsavings_file else None
    buyme = json.loads(Path(a.buyme_file).read_text(encoding='utf8')) if a.buyme_file else None
    print(json.dumps(build(a.seed,a.out,claw,buyme,a.buyme_minimum),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
