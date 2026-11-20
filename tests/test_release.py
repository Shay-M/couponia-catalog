from contextlib import closing
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.build import build
from src.release import (publication_decision, previous_from_dir,
                         enrichment_hash, normalize_enrichment)

ROOT = Path(__file__).resolve().parents[1]
TIME = datetime(2026, 11, 20, 16, 57, 42, tzinfo=timezone.utc)
CLAW = {'categories': {'fashion': {'sources': {
    'poalim_wonder': {'type': 'voucher', 'verified_at': '2026-03-06',
                      'deals': [{'store':'FOX','price':80,'face_value':100}]}
}}}}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)

    def make(self, dirname, clock=TIME, claw=CLAW):
        dest = self.path / dirname
        build(ROOT / 'seed/catalog-v2.db', dest, claw=claw, clock=clock)
        return dest

    def snapshot(self, directory):
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf8'))
        names = ('benefit_candidates.json', 'acceptance_candidates.json', 'sources.json')
        return manifest, {name: json.loads((directory/name).read_text(encoding='utf8')) for name in names}

    def test_no_change_does_not_bump_app_data_version_or_republish(self):
        old = self.make('old')
        old_release = publication_decision(old, None, clock=TIME)
        new = self.make('new', clock=TIME + timedelta(days=1))
        result = publication_decision(new, self.snapshot(old), clock=TIME + timedelta(days=1))
        self.assertFalse(result['changed'])
        self.assertFalse(result['coreChanged'])
        self.assertEqual(result['dataVersion'], old_release['dataVersion'])
        self.assertEqual(result['enrichmentVersion'], old_release['enrichmentVersion'])
        with closing(sqlite3.connect(new/'catalog.db')) as db:
            self.assertEqual(db.execute('SELECT data_version FROM catalog_meta').fetchone()[0],result['dataVersion'])

    def test_enrichment_only_keeps_android_version(self):
        old = self.make('old')
        old_release = publication_decision(old, None, clock=TIME)
        change = {'categories': {'fashion': {'sources': {
            'poalim_wonder': {'type': 'voucher', 'verified_at': '2026-03-06',
                              'deals': [{'store':'FOX','price':80,'face_value':100},
                                        {'store':'H&O','price':70,'face_value':100}]}
        }}}}
        new = self.make('new', clock=TIME+timedelta(days=1), claw=change)
        result = publication_decision(new, self.snapshot(old), clock=TIME+timedelta(days=1))
        self.assertTrue(result['changed'])
        self.assertFalse(result['coreChanged'])
        self.assertEqual(result['dataVersion'],old_release['dataVersion'])
        self.assertGreater(result['enrichmentVersion'],old_release['enrichmentVersion'])

    def test_core_change_advances_data_version(self):
        old = self.make('old')
        old_release = publication_decision(old, None, clock=TIME)
        new = self.make('new', clock=TIME+timedelta(days=1))
        fname=new/'cards.json'
        rows=json.loads(fname.read_text(encoding='utf-8'))
        rows[0]['name'] = 'CHANGE_FOR_TEST'
        fname.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
        manifest=json.loads((new/'manifest.json').read_text(encoding='utf8'))
        manifest['fileSha256']['cards.json']=hashlib.sha256(fname.read_bytes()).hexdigest()
        (new/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
        result=publication_decision(new,self.snapshot(old),clock=TIME+timedelta(days=1))
        self.assertTrue(result['coreChanged'])
        self.assertGreater(result['dataVersion'],old_release['dataVersion'])

    def test_sudden_candidate_loss_fails_closed(self):
        old = self.make('old')
        rows = json.loads((old/'benefit_candidates.json').read_text(encoding='utf8'))
        many = [dict(rows[0], id=f'deal{i}') for i in range(15)]
        (old/'benefit_candidates.json').write_text(json.dumps(many),encoding='utf8')
        manifest = json.loads((old/'manifest.json').read_text(encoding='utf8'))
        manifest['counts']['benefitCandidates']=15
        (old/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
        new = self.make('new', clock=TIME+timedelta(days=1), claw={'categories':{'x':{'sources':{}}}})
        with self.assertRaisesRegex(ValueError,'dropped'):
            publication_decision(new,self.snapshot(old),clock=TIME+timedelta(days=1))

    def test_missing_old_manifest_works_as_first_release(self):
        new=self.make('new')
        self.assertIsNone(previous_from_dir(self.path/'missing'))
        self.assertTrue(publication_decision(new,None,clock=TIME)['changed'])

    def test_bad_old_schema_rejected(self):
        old=self.make('old')
        old_manifest, old_files=self.snapshot(old)
        old_manifest['schemaVersion']=100
        new=self.make('new')
        with self.assertRaisesRegex(ValueError,'unsupported'):
            publication_decision(new,(old_manifest,old_files),clock=TIME)

    def test_import_time_change_is_not_new_data(self):
        sources=[{'id':'x', 'imported_at':'2026-11-20T00:00:00Z'}]
        self.assertEqual(normalize_enrichment('sources.json',sources),[{'id':'x'}])

    def test_same_enrichment_digest_for_changed_import_timestamp(self):
        files={'benefit_candidates.json':[], 'acceptance_candidates.json':[],
               'sources.json':[{'id':'x', 'imported_at':'2026-11-20T00:00:00Z'}]}
        other={**files,'sources.json':[{'id':'x','imported_at':'2026-11-21T00:00:00Z'}]}
        self.assertEqual(enrichment_hash(files),enrichment_hash(other))


if __name__=='__main__': unittest.main()

class LegacyManifestCompatibilityTests(unittest.TestCase):
    def test_old_manifest_without_enrichment_version_is_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            old=folder/'old'
            build(ROOT/'seed/catalog-v2.db',old,claw=CLAW,clock=TIME)
            prior_manifest=json.loads((old/'manifest.json').read_text(encoding='utf8'))
            # The last deployed manifest on 20 Nov 2026 did not have the new fields.
            prior_files={name:json.loads((old/name).read_text(encoding='utf8'))
                         for name in ('benefit_candidates.json','acceptance_candidates.json','sources.json')}
            new=folder/'new'
            build(ROOT/'seed/catalog-v2.db',new,claw=CLAW,clock=TIME+timedelta(days=1))
            decision=publication_decision(new,(prior_manifest,prior_files),clock=TIME+timedelta(days=1))
            self.assertTrue(decision['changed'])  # One-time manifest metadata upgrade
            self.assertFalse(decision['coreChanged'])
            self.assertEqual(decision['dataVersion'],prior_manifest['dataVersion'])
            self.assertEqual(decision['enrichmentVersion'],0)

class SourceWatcherTests(unittest.TestCase):
    def test_parses_public_commit_without_copying_catalog(self):
        from src.watch_sources import parse_commit
        commit={'sha':'a'*40,'commit':{'committer':{'date':'2026-11-19T10:20:30Z'}}}
        self.assertEqual(parse_commit([commit]), {'commit':'a'*12, 'committedAt':'2026-11-19T10:20:30Z'})

    def test_rejects_malformed_api_result(self):
        from src.watch_sources import parse_commit
        with self.assertRaises(ValueError):
            parse_commit([{'sha':'oops','commit':{}}])
