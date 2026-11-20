import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.build import build

ROOT = Path(__file__).resolve().parents[1]
CLOCK = datetime(2026,11,13,tzinfo=timezone.utc)
CLAW = {'categories': {'fashion': {'sources': {
    'poalim_wonder': {'type': 'voucher', 'verified_at': '2026-03-06',
                      'deals': [{'store':'FOX','price':80,'face_value':100}]},
    'htzone_card': {'type':'pos_discount','max_pct':20}
}}}}
BUYME = {'masterVoucherId':13438757,'businessCount':2, 'businesses':[
    {'id':123,'name':'FOX'}, {'id':124,'name':'Sample Store'}]}

class CatalogTest(unittest.TestCase):
    def generate(self, claw=CLAW, buyme=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name)
        report = build(ROOT/'seed/catalog-v2.db',path,claw,buyme,minimum=1,clock=CLOCK)
        return path,report

    def test_v2_relations_preserved_and_stale_offers_not_active(self):
        path,report=self.generate()
        self.assertEqual(report['counts']['cards'],99)
        self.assertEqual(report['schemaVersion'],3)
        self.assertEqual(report['dataVersion'],20261113000000)
        import hashlib
        for filename in ('cards.json','merchants.json','acceptance.json'):
            self.assertEqual(report['fileSha256'][filename],hashlib.sha256((path/filename).read_bytes()).hexdigest())
        self.assertEqual(report['counts']['merchants'],409)
        self.assertEqual(report['counts']['catalogCardMerchantLinks'],504)
        self.assertEqual(report['counts']['benefitCandidates'],1)
        self.assertEqual(report['counts']['freshBenefitCandidates'],0)
        with sqlite3.connect(path/'catalog.db') as c:
            self.assertEqual(c.execute('select freshness from benefit_candidates').fetchone()[0],'stale')
            self.assertEqual(c.execute('pragma user_version').fetchone()[0],3)
            self.assertEqual(c.execute('pragma foreign_key_check').fetchall(),[])

    def test_buyme_only_as_unverified_candidates(self):
        path,report=self.generate(buyme=BUYME)
        self.assertEqual(report['counts']['buymeAcceptanceCandidates'],2)
        with sqlite3.connect(path/'catalog.db') as c:
            self.assertEqual(c.execute("select count(*) from card_merchants where source_id='buyme-mcp'").fetchone()[0],0)

    def test_wrong_card_scope_rejected(self):
        with self.assertRaises(ValueError):
            self.generate(buyme={**BUYME, 'masterVoucherId':100})

    def test_bad_claw_format_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                build(ROOT/'seed/catalog-v2.db',d,claw={},clock=CLOCK)
            self.assertFalse((Path(d)/'catalog.db').exists())

if __name__=='__main__': unittest.main()
