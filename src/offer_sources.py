"""Shared source and declared-membership policy for offer publication.

A declaration only selects relevant offers. It is never proof of eligibility;
the issuer still checks card tier, points, quotas and purchase conditions.
"""
import re
from urllib.parse import urlsplit

from src.offer_contract import _nonempty


SOURCE_DOMAINS = {
    'max-benefits': ('max.co.il',),
    'isracard-benefits': ('isracard.co.il',),
    'cal-benefits': ('cal-online.co.il',),
    'amex-rewards': ('americanexpress.co.il',),
    'leumi-bonus': ('leumi.co.il',),
    'poalim-wonder': ('bankhapoalim.co.il',),
    'htzone-benefits': ('htzone.co.il',),
    'hot-club': ('hot.co.il', 'isracard.co.il', 'americanexpress.co.il'),
}

MEMBERSHIPS = {
    'max-card': 'max-benefits',
    'isracard-card': 'isracard-benefits',
    'cal-card': 'cal-benefits',
    'amex-card': 'amex-rewards',
    'leumi-bonus': 'leumi-bonus',
    'poalim-wonder': 'poalim-wonder',
    'htzone-member': 'htzone-benefits',
    'hot-visa': 'hot-club',
    'hot-mastercard': 'hot-club',
    'hot-amex': 'hot-club',
}


def official_domain(source_id, link):
    """Reject malformed URLs as data errors, never as a publisher crash."""
    if (not isinstance(source_id, str) or not _nonempty(link, 500)
            or any(c.isspace() for c in link) or any(c in '<>"{}|\\^`' for c in link)
            or re.search(r'%(?![0-9a-fA-F]{2})', link)
            or any(ord(c) < 32 or ord(c) == 127 for c in link)):
        return False
    try:
        parsed = urlsplit(link)
        if (parsed.scheme != 'https' or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)):
            return False
        host = (parsed.hostname or '').lower()
        return any(host == suffix or host.endswith('.' + suffix)
                   for suffix in SOURCE_DOMAINS.get(source_id, ()))
    except (ValueError, TypeError):
        return False
