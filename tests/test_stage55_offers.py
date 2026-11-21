import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from src.publish_offers import build, official_domain

NOW = datetime(2026,11,21,8,0,tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]

def ts(when):return when.strftime('%Y-%m-%dT%H:%M:%SZ')

class TestPublishedOffers(unittest.TestCase):
    def setup_files(self, path, offers, grants):
        inputs = [dict(schemaVersion=1, offers=offers), dict(schemaVersion=1, grants=grants)]
        output=[]
        for index, data in enumerate(inputs):
            location = path/f'input_{index}.json'
            location.write_text(json.dumps(data), encoding='utf-8'); output.append(location)
        return output

    def offer(self):
        return dict(offerId='test-1',sourceId='max-benefits',issuerProductId='MAX-TEST',
            merchantName='רשת בדיקה',titleHe='הטבת בדיקה',titleEn='Demo benefit',
            eligibilitySummary='Eligible demo cardholders only',termsSummary='Demo terms',
            offerType='voucher_discount', issuerEvidenceUrl='https://www.max.co.il/benefits/demo',
            rightsBasis='written_issuer_permission',verificationStatus='issuer_verified',stockStatus='available',
            checkedAt=ts(NOW-timedelta(hours=1)),validFrom=ts(NOW-timedelta(days=1)),
            validUntil=ts(NOW+timedelta(days=2)))

    def grant(self):
        return dict(sourceId='max-benefits',approvedForRedistribution=True,
                    rightsBasis='written_issuer_permission',grantReference='TEST-only-letter-2026',
                    validUntil=ts(NOW+timedelta(days=3)))

    def run_build(self, offers, grants):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); a,g=self.setup_files(base,offers,grants)
            registry=json.loads((ROOT/'config/offer_source_registry.json').read_text())
            for source in registry['sources']: source['enabled']=True
            registry_path=base/'registry.json'; registry_path.write_text(json.dumps(registry))
            report=build(a,g,registry_path,base/'dist',NOW)
            offer_bytes=(base/'dist/offers.json').read_bytes()
            manifest=json.loads((base/'dist/manifest.json').read_text())
            return report, json.loads(offer_bytes), manifest, offer_bytes

    def test_unapproved_sources_never_publish(self):
        report, rows, _, _=self.run_build([self.offer()], [])
        self.assertEqual(rows,[]); self.assertEqual(report['published'],0)
        self.assertIn('no_active_explicit_source_permission',report['exclusionReasons'])

    def test_expired_offer_or_stale_observation_fail_closed(self):
        o=self.offer(); o['checkedAt']=ts(NOW-timedelta(days=4)); o['validUntil']=ts(NOW-timedelta(hours=1))
        report,rows,_,_=self.run_build([o],[self.grant()]); self.assertEqual(rows,[])
        self.assertIn('not_freshly_checked',report['exclusionReasons'])
        self.assertIn('not_in_validity_window',report['exclusionReasons'])

    def test_issuer_domain_blocks_phishing(self):
        self.assertFalse(official_domain('max-benefits','https://www.max.co.il.evil.net/offer'))
        self.assertFalse(official_domain('max-benefits','http://www.max.co.il/offer'))
        self.assertTrue(official_domain('max-benefits','https://www.max.co.il/offer'))
        o=self.offer(); o['issuerEvidenceUrl']='https://www.max.co.il.fake.com/offer'
        report,rows,_,_=self.run_build([o],[self.grant()]); self.assertEqual(rows,[])
        self.assertIn('non_issuer_domain',report['exclusionReasons'])

    def test_valid_licensed_offer_sanitizes_and_hashes(self):
        report,rows,manifest,source=self.run_build([self.offer()],[self.grant()])
        self.assertEqual(len(rows),1)
        self.assertEqual(report['published'],1)
        self.assertEqual(manifest['fileSha256']['offers.json'],hashlib.sha256(source).hexdigest())
        self.assertEqual(manifest['counts']['offers'],1)
        self.assertNotIn('grantReference',rows[0])

    def test_duplicate_id_fails_whole_publication(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.run_build([self.offer(),self.offer()],[self.grant()])

    def test_real_inputs_publish_no_unapproved_discounts(self):
        with tempfile.TemporaryDirectory() as d:
            report=build(ROOT/'config/approved_offers.json',ROOT/'config/offer_rights_grants.json',
                  ROOT/'config/offer_source_registry.json',Path(d),NOW)
            self.assertEqual(report['published'],0)
            self.assertEqual(json.loads((Path(d)/'offers.json').read_text()),[])

if __name__=='__main__':unittest.main()

# Tests added below remain available to unittest discovery via an independent class.
class CompareOffersTests(unittest.TestCase):
    def test_no_change_when_published_payload_hash_matches(self):
        from unittest.mock import patch
        from src.compare_offers import changed
        class Response:
            status = 200
            def read(self, n):
                return b'{"fileSha256":{"offers.json":"same"}}'
            def __enter__(self): return self
            def __exit__(self,*args): pass
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'manifest.json'
            p.write_text('{"fileSha256":{"offers.json":"same"}}')
            with patch('src.compare_offers.urlopen', return_value=Response()):
                self.assertFalse(changed(p,'https://example.org/manifest.json'))

    def test_missing_previous_payload_triggers_deployment(self):
        from unittest.mock import patch
        from src.compare_offers import changed
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'manifest.json'
            p.write_text('{"fileSha256":{"offers.json":"new"}}')
            with patch('src.compare_offers.urlopen', side_effect=OSError('offline')):
                self.assertTrue(changed(p,'https://example.org/manifest.json'))
