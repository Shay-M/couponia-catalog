"""Couponia v3.4: strictly product-scoped manual issuer updates."""
import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from src.build import build
from src.catalog_guard import SnapshotRegression, assert_additive

ROOT=Path(__file__).resolve().parents[1]
CURATED=json.loads((ROOT/'config/curated_issuer_facts.json').read_text(encoding='utf-8'))
NOW=datetime(2026,11,21,1,48,tzinfo=timezone.utc)


class CatalogV34Tests(unittest.TestCase):
    def build(self, folder, curated=CURATED):
        return build(ROOT/'seed/catalog-v2.db',folder,clock=NOW,curated=curated)

    def test_growth_and_immutable_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            result=self.build(folder)
            counts=result['counts']
            self.assertEqual((counts['cards'],counts['catalogCardMerchantLinks']),(108,648))
            self.assertGreaterEqual(counts['merchants'],409)
            self.assertEqual((counts['curatedExistingCardLinks'],counts['curatedProductReviews']),(19,1))
            self.assertEqual(result['schemaVersion'],3)
            delta=assert_additive(ROOT/'seed/catalog-v2.db',Path(folder)/'catalog.db')
            self.assertEqual((delta['cardsAdded'],delta['linksAdded']),(9,144))
            self.assertGreaterEqual(delta['merchantsAdded'],0)
            for key in ('cards.json','merchants.json','acceptance.json'):
                self.assertIn(key,result['fileSha256'])
            self.assertFalse((Path(folder)/'offers.json').exists())

    def test_precise_product_scope_and_restrictions(self):
        with tempfile.TemporaryDirectory() as folder:
            self.build(folder)
            with closing(sqlite3.connect(Path(folder)/'catalog.db')) as db:
                for cid,total in (('htzone-giftzone',23),('buyme-baby',8),('buyme-brunch',4),('buyme-local',7)):
                    self.assertEqual(db.execute('SELECT count(*) FROM card_merchants WHERE card_id=?',(cid,)).fetchone()[0],total)
                self.assertEqual(db.execute("SELECT count(*) FROM card_merchants WHERE card_id='swish-plus'").fetchone()[0],0)
                self.assertIn('product-105984',db.execute("SELECT source_url FROM cards WHERE id='swish-plus'").fetchone()[0])
                self.assertEqual(db.execute("SELECT evidence_level FROM sources WHERE id='swish-plus-product-official-20261121'").fetchone()[0],'issuer_product')
                swarovski=db.execute("SELECT listing_scope,redemption_channel,restriction_note FROM card_merchants WHERE card_id='htzone-giftzone' AND listed_name='SWAROVSKI'").fetchone()
                self.assertEqual(swarovski[:2],('selected_branches','in_store'))
                self.assertIn('specified physical branches',swarovski[2])
                self.assertEqual(db.execute("SELECT redemption_channel FROM card_merchants WHERE card_id='htzone-giftzone' AND listed_name='JanSport'").fetchone()[0],'online')
                self.assertEqual(db.execute("SELECT count(*) FROM card_merchants WHERE card_id='buyme-brunch' AND listing_scope='selected_branches'").fetchone()[0],1)

    def test_v33_reference_not_shrunk(self):
        with tempfile.TemporaryDirectory() as folder:
            old,new=Path(folder)/'old',Path(folder)/'new'
            former=copy.deepcopy(CURATED)
            former['cards'].pop()
            former.pop('existingCards');former.pop('productReviews')
            build(ROOT/'seed/catalog-v2.db',old,clock=NOW,curated=former)
            self.build(new)
            delta=assert_additive(old/'catalog.db',new/'catalog.db')
            self.assertEqual((delta['cardsAdded'],delta['linksAdded']),(1,42))
            self.assertGreaterEqual(delta['merchantsAdded'],0)

    def test_extension_mismatch_and_wrong_domain_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for kind in ('unknown_id','wrong_issuer','bad_domain','empty_list'):
                altered=copy.deepcopy(CURATED)
                row=altered['existingCards'][0]
                if kind=='unknown_id':row['cardId']='card-not-in-the-seed'
                elif kind=='wrong_issuer':row['issuer']='MAX'
                elif kind=='bad_domain':row['sourceUrl']='https://example.com/brands/9018727'
                else:row['merchants']=[]
                with self.assertRaises(ValueError,msg=kind):
                    self.build(Path(folder)/kind,altered)

    def test_product_review_never_infers_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            altered=copy.deepcopy(CURATED)
            altered['productReviews'][0]['merchants']=['FOX']
            with self.assertRaisesRegex(ValueError,'may not contain merchant'):
                self.build(folder,altered)

    def test_guard_detects_deleted_original_link(self):
        with tempfile.TemporaryDirectory() as folder:
            self.build(folder)
            with closing(sqlite3.connect(Path(folder)/'catalog.db')) as db:
                link=db.execute('SELECT card_id,merchant_id FROM card_merchants WHERE source_id=? LIMIT 1',('swish_catalog',)).fetchone()
                self.assertIsNotNone(link)
                db.execute('DELETE FROM card_merchants WHERE card_id=? AND merchant_id=?',link)
                db.commit()
            with self.assertRaisesRegex(SnapshotRegression,'deleted'):
                assert_additive(ROOT/'seed/catalog-v2.db',Path(folder)/'catalog.db')

    def test_research_sources_disabled(self):
        for filename in ('source_registry_research.json','offer_source_registry.json'):
            data=json.loads((ROOT/'config'/filename).read_text(encoding='utf-8'))
            self.assertTrue(data.get('defaultEnabled') is False or data.get('enabledByDefault') is False)
            self.assertTrue(all(s.get('enabled') is False for s in data['sources']))

if __name__=='__main__':unittest.main()
