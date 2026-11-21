"""Regression tests for real publication hazards and the exact purchase chain.

All offers/memberships here are synthetic test data. Production approved_offers
and grants stay empty; these fixtures never become public recommendations.
"""
from contextlib import closing
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.build import as_number
from src.curation import get_or_create_merchant, observation
from src.publish_offers import build, check_grants
from src.offer_sources import official_domain
from src.purchase_contract import CatalogEvidence, purchase_reasons

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)


def stamp(t):
    return t.isoformat().replace('+00:00', 'Z')


def offer():
    return {
        'offerId': 'test-voucher', 'sourceId': 'hot-club', 'issuerProductId': 'HOT-TEST',
        'merchantName': 'Test supermarket', 'titleHe': 'בדיקה בלבד', 'titleEn': 'Test only',
        'eligibilitySummary': 'Issuer checks all conditions', 'termsSummary': 'Test conditions',
        'offerType': 'voucher_discount', 'issuerEvidenceUrl': 'https://www.hot.co.il/test-only',
        'rightsBasis': 'owned_data', 'verificationStatus': 'issuer_verified', 'stockStatus': 'available',
        'checkedAt': stamp(NOW - timedelta(hours=1)), 'validFrom': stamp(NOW - timedelta(days=1)),
        'validUntil': stamp(NOW + timedelta(days=2)),
        'purchase': {
            'voucherCardId': 'test-card', 'merchantIds': ['test-store'],
            'redemptionChannel': 'in_store', 'membershipIds': ['hot-visa'],
            'faceValueMinor': 10_000, 'priceMinor': 9_000, 'currency': 'ILS',
            'purchaseUrl': 'https://www.hot.co.il/test-only', 'conditionsSummary': 'Test-only conditions',
        },
    }


def grant():
    return {'sourceId': 'hot-club', 'approvedForRedistribution': True, 'rightsBasis': 'owned_data',
            'grantReference': 'SYNTHETIC-TEST-DATA', 'validUntil': stamp(NOW + timedelta(days=3))}


def evidence(scope='network', channel='in_store', card='test-card', merchant='test-store'):
    return CatalogEvidence(frozenset({card}), frozenset({merchant}),
                           {(card, merchant): ('listed', scope, channel)})


class PurchaseContractTests(unittest.TestCase):
    def test_exact_product_merchant_and_channel_required(self):
        self.assertEqual(purchase_reasons(offer(), evidence()), [])
        for bad in (evidence(merchant='parent-chain'), evidence(card='different-voucher'),
                    evidence(channel='online'), evidence(channel='unknown'), evidence(scope='selected_branches'),
                    evidence(scope='location_or_restricted'), evidence(scope='unspecified')):
            with self.subTest(evidence=bad):
                self.assertIn('purchase_catalog_evidence_mismatch', purchase_reasons(offer(), bad))
        self.assertIn('purchase_catalog_evidence_missing', purchase_reasons(offer(), None))

    def test_both_does_not_mean_either_and_online_scope_not_physical(self):
        row=offer(); row['purchase']['redemptionChannel']='both'
        self.assertIn('purchase_catalog_evidence_mismatch',purchase_reasons(row,evidence(channel='online')))
        self.assertEqual(purchase_reasons(row,evidence(channel='both')),[])
        row['purchase']['redemptionChannel']='in_store'
        self.assertIn('purchase_catalog_evidence_mismatch',purchase_reasons(row,evidence(scope='online',channel='both')))
        row['purchase']['redemptionChannel']='online'
        self.assertEqual(purchase_reasons(row,evidence(scope='online',channel='online')),[])

    def test_membership_does_not_cross_sources_or_infer_hot_product(self):
        row=offer()
        for bad in (['htzone-member'], ['isracard-card'], ['hot-unknown'], [], ['hot-visa','hot-visa']):
            row['purchase']['membershipIds']=bad
            self.assertIn('invalid_purchase_memberships',purchase_reasons(row,evidence()))
        row['purchase']['membershipIds']=['hot-mastercard','hot-amex']
        self.assertEqual(purchase_reasons(row,evidence()),[])

    def test_money_requires_integer_minor_units_and_positive_savings(self):
        row=offer()
        for field,value in (('priceMinor',True),('priceMinor',9000.0),('priceMinor','9000'),
                            ('priceMinor',0),('priceMinor',10_000),('priceMinor',-1),
                            ('faceValueMinor',1_000_000_000_001)):
            sample=copy.deepcopy(row); sample['purchase'][field]=value
            self.assertIn('invalid_purchase_amounts',purchase_reasons(sample,evidence()))

    def test_malformed_or_spoofed_urls_fail_without_exception(self):
        bad=[None,5,[],{},'https://www.hot.co.il:bad/','https://[invalid/',
             'https://www.hot.co.il.evil.test/','https://hot.co.il@evil.test/',
             'https://@hot.co.il/','https://www.hot.co.il\n/','http://www.hot.co.il/',
             'https://www.hot.co.il/%XX', 'https://www.hot.co.il/path|invalid']
        for url in bad:
            self.assertFalse(official_domain('hot-club',url),url)
            row=offer(); row['purchase']['purchaseUrl']=url
            self.assertIn('non_issuer_purchase_url',purchase_reasons(row,evidence()))
        self.assertTrue(official_domain('hot-club','https://www.isracard.co.il/credit-cards/moadonhot'))

    def test_duplicate_ids_null_purchase_and_non_voucher_are_rejected(self):
        for changes,reason in [({'merchantIds':['test-store','test-store']},'invalid_purchase_catalog_ids'),
                               ({'merchantIds':[]},'invalid_purchase_catalog_ids'),
                               ({'conditionsSummary':''},'missing_purchase_conditions')]:
            row=offer(); row['purchase'].update(changes)
            self.assertIn(reason,purchase_reasons(row,evidence()))
        row=offer(); row['purchase']=None
        self.assertEqual(purchase_reasons(row,evidence()),['invalid_purchase_shape'])
        row=offer();row['offerType']='cashback'
        self.assertIn('purchase_requires_voucher_discount',purchase_reasons(row,evidence()))


class PublicationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)

    def publish(self,rows,grants=None,enabled=True):
        registry=json.loads((ROOT/'config/offer_source_registry.json').read_text())
        for source in registry['sources']:
            if source['id']=='hot-club':source['enabled']=enabled
        payloads=[{'schemaVersion':1,'offers':rows},{'schemaVersion':1,'grants':grants or [grant()]},registry]
        paths=[]
        for i,data in enumerate(payloads):
            p=self.path/f'{i}.json';p.write_text(json.dumps(data));paths.append(p)
        result=build(*paths,self.path/'out',now=NOW,catalog_dir=self.write_evidence())
        return result,json.loads((self.path/'out/offers.json').read_text())

    def write_evidence(self):
        p=self.path/'catalog';p.mkdir(exist_ok=True)
        payloads={'cards.json':[{'id':'test-card'}],'merchants.json':[{'id':'test-store'}],
                  'acceptance.json':[{'card_id':'test-card','merchant_id':'test-store','status':'listed',
                                      'listing_scope':'network','redemption_channel':'in_store'}]}
        hashes={}
        for filename,rows in payloads.items():
            raw=json.dumps(rows).encode();(p/filename).write_bytes(raw);hashes[filename]=hashlib.sha256(raw).hexdigest()
        (p/'manifest.json').write_text(json.dumps({'schemaVersion':3,'counts':{'cards':1,'merchants':1,'catalogCardMerchantLinks':1},'fileSha256':hashes}))
        return p

    def test_disabled_source_cannot_publish_even_with_valid_grant(self):
        result,rows=self.publish([offer()],enabled=False)
        self.assertEqual(rows,[]);self.assertIn('source_disabled',result['exclusionReasons'])

    def test_published_expiry_cannot_outlive_source_grant(self):
        g=grant();g['validUntil']=stamp(NOW+timedelta(hours=2))
        result,rows=self.publish([offer()],[g])
        self.assertEqual(result['published'],1)
        self.assertEqual(rows[0]['validUntil'],g['validUntil'])
        self.assertNotIn('grantReference',rows[0]);self.assertEqual(rows[0]['purchase'],offer()['purchase'])

    def test_malformed_offer_does_not_block_other_valid_records(self):
        bad=offer();bad.update(offerId='malformed',issuerEvidenceUrl={},offerType=[],rightsBasis=[])
        result,rows=self.publish([bad,offer()])
        self.assertEqual(result['excluded'],1);self.assertEqual(len(rows),1)

    def test_field_overflow_that_android_rejects_is_excluded(self):
        for text in ('x'*501, '\U0001f6d2'*251, ' leading whitespace'):
            bad=offer();bad['eligibilitySummary']=text
            result,rows=self.publish([bad])
            self.assertEqual(rows,[]);self.assertIn('missing_eligibilitySummary',result['exclusionReasons'])

    def test_duplicate_expired_grants_cannot_bypass_duplicate_guard(self):
        g=grant();g['validUntil']=stamp(NOW-timedelta(days=1))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            check_grants({'schemaVersion':1,'grants':[g,grant()]},NOW)

    def test_catalog_hash_mismatch_blocks_purchase_evidence(self):
        p=self.write_evidence();(p/'merchants.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'checksum'):
            CatalogEvidence.from_directory(p)


class CatalogInputRegressionTests(unittest.TestCase):
    def test_ambiguous_normalized_name_does_not_create_third_merchant(self):
        with closing(sqlite3.connect(':memory:')) as db:
            db.executescript('CREATE TABLE merchants(id TEXT PRIMARY KEY,name TEXT,normalized_name TEXT);'
                             'CREATE TABLE merchant_aliases(alias TEXT,merchant_id TEXT);')
            db.executemany('INSERT INTO merchants VALUES(?,?,?)',[('a','FOO-BAR','foo bar'),('b','FOO BAR','foo bar')])
            with self.assertRaisesRegex(ValueError,'Ambiguous'):
                get_or_create_merchant(db,'FOO BAR')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM merchants').fetchone()[0],2)

    def test_impossible_observation_date_is_rejected(self):
        with self.assertRaises(ValueError):observation('2026-02-31T12:00:00Z')
        with self.assertRaises(ValueError):observation('2026-02-01T25:00:00Z')

    def test_nonfinite_upstream_prices_cannot_produce_invalid_json(self):
        for value in ('Infinity','NaN',float('inf'),float('nan'),True):
            self.assertIsNone(as_number(value))
        self.assertEqual(as_number('12.5'),12.5)


if __name__=='__main__':unittest.main()
