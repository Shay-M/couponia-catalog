"""Deterministic exact merchant alias matching; never fuzzy-guess voucher acceptance."""
import re
import unicodedata


def normalize(value):
    s = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ' '.join(re.sub(r'[^\w\u0590-\u05ff]+', ' ', s).split())


def match_names(db):
    aliases = {}
    for mid, name in db.execute('SELECT id,name FROM merchants'):
        aliases.setdefault(normalize(name), set()).add(mid)
    for alias, mid in db.execute('SELECT alias, merchant_id FROM merchant_aliases'):
        aliases.setdefault(normalize(alias), set()).add(mid)
    return {key: next(iter(ids)) for key, ids in aliases.items() if key and len(ids) == 1}
