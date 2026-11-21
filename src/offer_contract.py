"""Validation contract for FUTURE credit-card and club offer feeds.

No offers are collected by this module. It does not alter the Android v3
catalog schema or label research candidates as valid current discounts.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import re
from urllib.parse import urlsplit

ALLOWED_TYPES = {'voucher_discount','cashback','pos_discount','coupon_code',
                 'points_redemption','two_for_one','gift_card_bonus'}
ALLOWED_RIGHTS = {'licensed_feed','written_issuer_permission','owned_data'}
MAX_RECHECK_HOURS = 36
STRING_LIMITS = {
    'offerId': 160, 'sourceId': 100, 'issuerProductId': 500, 'merchantName': 500,
    'titleHe': 500, 'titleEn': 500, 'eligibilitySummary': 500, 'termsSummary': 500,
    'offerType': 80, 'issuerEvidenceUrl': 500, 'rightsBasis': 80,
    'verificationStatus': 60, 'stockStatus': 40,
    'checkedAt': 60, 'validFrom': 60, 'validUntil': 60,
}


def _utc(value):
    if (not isinstance(value,str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z', value)):
        raise ValueError('Expected UTC ISO timestamp')
    stamp=datetime.fromisoformat(value[:-1] + '+00:00')
    if stamp.utcoffset()!=timedelta(0):
        raise ValueError('Expected UTC')
    return stamp


def _nonempty(value, limit=500):
    if (not isinstance(value, str) or not value or value != value.strip() or value == 'null'):
        return False
    try:
        # Android String.length counts UTF-16 code units, including two per emoji.
        return len(value.encode('utf-16-le')) // 2 <= limit
    except UnicodeEncodeError:
        return False


def _issuer_link(value):
    if not _nonempty(value):
        return False
    if any(c.isspace() for c in value) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    try:
        p=urlsplit(value)
        return (p.scheme=='https' and bool(p.hostname) and p.username is None
                and p.password is None and p.port in (None, 443))
    except ValueError:
        return False


def check_offer_publication(offer, now=None):
    """Return publishable/reasons; fail closed on missing terms or access rights."""
    now=now or datetime.now(timezone.utc)
    reasons=[]
    if not isinstance(offer,dict):
        return {'publishable':False, 'reasons':['offer_not_object']}
    for k, limit in STRING_LIMITS.items():
        if not _nonempty(offer.get(k), limit):
            reasons.append('missing_'+k)
    if not isinstance(offer.get('offerType'), str) or offer['offerType'] not in ALLOWED_TYPES:
        reasons.append('unknown_offer_type')
    if not _issuer_link(offer.get('issuerEvidenceUrl')):
        reasons.append('no_https_issuer_evidence')
    if not isinstance(offer.get('rightsBasis'), str) or offer['rightsBasis'] not in ALLOWED_RIGHTS:
        reasons.append('no_redistribution_rights')
    if offer.get('verificationStatus') != 'issuer_verified':
        reasons.append('not_issuer_verified')
    if offer.get('stockStatus') != 'available':
        reasons.append('unavailable_or_unknown_stock')
    try:
        checked=_utc(offer.get('checkedAt'))
        if checked > now + timedelta(minutes=5) or (now-checked) > timedelta(hours=MAX_RECHECK_HOURS):
            reasons.append('not_freshly_checked')
    except (ValueError, TypeError):
        reasons.append('missing_checked_at')
    try:
        start=_utc(offer.get('validFrom'))
        end=_utc(offer.get('validUntil'))
        if not start <= now < end or end <= start:
            reasons.append('not_in_validity_window')
    except (ValueError, TypeError):
        reasons.append('missing_validity_window')
    return {'publishable':not reasons, 'reasons':sorted(set(reasons))}
