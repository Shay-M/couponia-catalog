"""Regression checks for manually reviewed issuer facts and no false POS claims."""
import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

from src.build import build
from src.review_status import overdue_cards
from importlib.util import find_spec
if find_spec('src.release') is not None:
    from src.release import publication_decision
else:
    publication_decision = None  # Included in full GitHub repo, not this update ZIP.

ROOT = Path(__file__).resolve().parents[1]
CLOCK = datetime(2026, 11, 21, 1, 0, 0, tzinfo=timezone.utc)
CURATED = json.loads((ROOT/'config/curated_issuer_facts.json').read_text(encoding='utf8'))


class CuratedIssuerTests(unittest.TestCase):
    def make(self, folder, curation=CURATED, clock=CLOCK):
        return build(ROOT/'seed/catalog-v2.db', folder, curated=curation, clock=clock)

    def test_review_window_does_not_affect_core_json(self):
        self.assertEqual(overdue_cards(CURATED, date(2026, 11, 25), 60), [])
        self.assertEqual(len(overdue_cards(CURATED, date(2027, 2, 1), 60)), 13)

    def test_actual_growth_and_app_compatibility(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.make(temp)
            self.assertEqual(result['schemaVersion'], 3)
            self.assertEqual(result['counts']['cards'], 108)
            self.assertGreaterEqual(result['counts']['merchants'], 409)
            self.assertEqual(result['counts']['catalogCardMerchantLinks'], 648)
            self.assertEqual(result['counts']['curatedIssuerCards'], 9)
            self.assertEqual(result['counts']['curatedIssuerLinks'], 125)
            with closing(sqlite3.connect(Path(temp)/'catalog.db')) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
                self.assertEqual(db.execute("SELECT COUNT(*) FROM card_merchants WHERE source_id LIKE 'isracard-%'").fetchone()[0], 56)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM card_merchants WHERE source_id LIKE 'isracard-%' AND status != 'listed'").fetchone()[0], 0)
            for name, table in (('cards.json','cards'),('merchants.json','merchants'),('acceptance.json','card_merchants')):
                with closing(sqlite3.connect(ROOT/'seed/catalog-v2.db')) as baseline_db:
                    cur = baseline_db.execute('SELECT * FROM ' + table + ' LIMIT 0')
                    expected = {d[0] for d in cur.description}
                upgraded = json.loads((Path(temp)/name).read_text(encoding='utf-8'))
                self.assertEqual(expected, set(upgraded[0].keys()))

    def test_precise_product_scope_no_cross_assignment(self):
        with tempfile.TemporaryDirectory() as temp:
            self.make(temp)
            with closing(sqlite3.connect(Path(temp)/'catalog.db')) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM card_merchants WHERE card_id=?', ('isracard-gift-card',)).fetchone()[0], 14)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM card_merchants WHERE card_id=?', ('isracard-gift-card-isracard',)).fetchone()[0], 14)
                for cid, expected in (
                    ('max-gift-card', 18), ('max-super-gift-card', 20),
                    ('gifta-gift-card', 8), ('gifta-food', 0),
                    ('isracard-digital-gift-card', 14),
                    ('isracard-gift-card-shopping', 14)):
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM card_merchants WHERE card_id=?', (cid,)).fetchone()[0], expected)
                # Food retailers in Super must not be assigned to ordinary MAX Gift Card.
                self.assertEqual(db.execute("SELECT COUNT(*) FROM card_merchants WHERE card_id='max-gift-card' AND listed_name='ויקטורי'").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM card_merchants WHERE card_id='max-super-gift-card' AND listed_name='ויקטורי'").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM card_merchants WHERE card_id='max-gift-card' AND listed_name='ACE' AND restriction_note LIKE '%Issuer leaflet%'").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM card_merchants WHERE card_id='isracard-gift-card' AND listed_name='ויקטורי'").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM card_merchants WHERE card_id='isracard-gift-card-isracard' AND listed_name='FOX'").fetchone()[0], 0)

    def test_existing_alias_canonical_merchant_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            self.make(temp)
            with closing(sqlite3.connect(Path(temp)/'catalog.db')) as db:
                mid = db.execute("SELECT id FROM merchants WHERE name='NINE WEST'").fetchone()[0]
                other = db.execute("SELECT merchant_id FROM card_merchants WHERE card_id='isracard-gift-card' AND listed_name='ניין ווסט'").fetchone()[0]
                self.assertEqual(mid, other)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM merchants WHERE name='ניין ווסט'").fetchone()[0], 0)

    def test_bad_issuer_url_fails_closed_without_output_db(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = copy.deepcopy(CURATED)
            fake['cards'][0]['sourceUrl'] = 'http://localhost/cards'
            with self.assertRaises(ValueError):
                self.make(temp, fake)
            self.assertFalse((Path(temp)/'catalog.db').exists())

    def test_invalid_existing_merchant_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = copy.deepcopy(CURATED)
            fake['cards'][0]['merchants'][0]['existingName'] = 'This merchant is not in the catalog'
            with self.assertRaisesRegex(ValueError, 'Unknown approved existing merchant'):
                self.make(temp, fake)
            self.assertFalse((Path(temp)/'catalog.db').exists())

    def test_restriction_note_length_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = copy.deepcopy(CURATED)
            fake['cards'][2]['merchants'][12]['restrictionNote'] = 'x' * 351
            with self.assertRaisesRegex(ValueError, 'restrictionNote'):
                self.make(temp, fake)
            self.assertFalse((Path(temp)/'catalog.db').exists())

    def test_max_source_is_not_shared_between_product_variants(self):
        with tempfile.TemporaryDirectory() as temp:
            self.make(temp)
            with closing(sqlite3.connect(Path(temp)/'catalog.db')) as db:
                a = db.execute("SELECT source_url FROM cards WHERE id='max-gift-card'").fetchone()[0]
                b = db.execute("SELECT source_url FROM cards WHERE id='max-super-gift-card'").fetchone()[0]
                self.assertNotEqual(a, b)
                self.assertIn('gc-max-digital.pdf', a)
                self.assertIn('gc-max-super.pdf', b)

    def test_duplicate_card_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = copy.deepcopy(CURATED)
            fake['cards'].append(copy.deepcopy(fake['cards'][0]))
            with self.assertRaisesRegex(ValueError, 'Duplicate or invalid'):
                self.make(temp, fake)

    @unittest.skipUnless(publication_decision, 'Needs src/release.py from the full repository')
    def test_same_manual_input_does_not_bump_version(self):
        with tempfile.TemporaryDirectory() as temp:
            old, new = Path(temp)/'old', Path(temp)/'new'
            self.make(old)
            previous = publication_decision(old, None, clock=CLOCK)
            self.make(new, clock=CLOCK + timedelta(days=1))
            oldm = json.loads((old/'manifest.json').read_text(encoding='utf8'))
            extras = {name:json.loads((old/name).read_text(encoding='utf8'))
                      for name in ('benefit_candidates.json','acceptance_candidates.json','sources.json')}
            result = publication_decision(new,(oldm,extras),clock=CLOCK+timedelta(days=1))
            self.assertFalse(result['changed'])
            self.assertFalse(result['coreChanged'])
            self.assertEqual(result['dataVersion'],previous['dataVersion'])

    @unittest.skipUnless(publication_decision, 'Needs src/release.py from the full repository')
    def test_curated_import_is_a_real_core_change(self):
        with tempfile.TemporaryDirectory() as temp:
            old, new = Path(temp)/'old', Path(temp)/'new'
            build(ROOT/'seed/catalog-v2.db',old,clock=CLOCK)
            publication_decision(old,None,clock=CLOCK)
            oldm = json.loads((old/'manifest.json').read_text(encoding='utf8'))
            extras = {name:json.loads((old/name).read_text(encoding='utf8'))
                      for name in ('benefit_candidates.json','acceptance_candidates.json','sources.json')}
            self.make(new,clock=CLOCK+timedelta(days=1))
            result = publication_decision(new,(oldm,extras),clock=CLOCK+timedelta(days=1))
            self.assertTrue(result['changed'])
            self.assertTrue(result['coreChanged'])
            self.assertGreater(result['dataVersion'],oldm['dataVersion'])


if __name__ == '__main__':
    unittest.main()
