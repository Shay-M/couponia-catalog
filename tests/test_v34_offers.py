"""Future offer schema is NOT an enabled offer ingest or Android feature."""
import unittest
from datetime import datetime,timezone,timedelta
from src.offer_contract import check_offer_publication

NOW=datetime(2026,11,21,1,48,tzinfo=timezone.utc)

def stamp(time):return time.strftime('%Y-%m-%dT%H:%M:%SZ')

def valid_demo():
    return {
        'offerId':'TEST-ONLY','sourceId':'fictional-demo',
        'issuerProductId':'specific-demo-card-or-club','merchantName':'Demo Store',
        'eligibilitySummary':'Specific club members only','offerType':'voucher_discount',
        'titleHe':'הטבת בדיקה','titleEn':'Test offer','termsSummary':'Test conditions',
        'issuerEvidenceUrl':'https://example.org/fictional-offer',
        'rightsBasis':'written_issuer_permission','verificationStatus':'issuer_verified',
        'stockStatus':'available','checkedAt':stamp(NOW-timedelta(hours=1)),
        'validFrom':stamp(NOW-timedelta(days=1)),
        'validUntil':stamp(NOW+timedelta(days=3))
    }

class FutureOfferContractTests(unittest.TestCase):
    def test_complete_fictional_offer_contract(self):
        self.assertTrue(check_offer_publication(valid_demo(),NOW)['publishable'])

    def test_rights_and_eligibility_required(self):
        offer=valid_demo();offer.pop('rightsBasis');offer.pop('issuerProductId')
        report=check_offer_publication(offer,NOW)
        self.assertFalse(report['publishable'])
        self.assertIn('no_redistribution_rights',report['reasons'])
        self.assertIn('missing_issuerProductId',report['reasons'])

    def test_expired_stale_and_unverified_are_never_active(self):
        offer=valid_demo()
        offer.update({'validUntil':'2026-11-01T01:00:00Z','verificationStatus':'unverified',
                      'stockStatus':'unknown','checkedAt':'2026-11-01T01:00:00Z'})
        report=check_offer_publication(offer,NOW)
        self.assertFalse(report['publishable'])
        for reason in ('not_freshly_checked','unavailable_or_unknown_stock','not_in_validity_window'):
            self.assertIn(reason,report['reasons'])

    def test_missing_expiry_does_not_default_to_active(self):
        offer=valid_demo();offer.pop('validUntil')
        report=check_offer_publication(offer,NOW)
        self.assertFalse(report['publishable'])
        self.assertIn('missing_validity_window',report['reasons'])

if __name__=='__main__':unittest.main()
