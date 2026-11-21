"""A previous v3 addition must not disappear under the old ten-percent gate."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from src.build import build
from src.catalog_guard import SnapshotRegression
from src.release import publication_decision, previous_from_dir

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 21, 10, tzinfo=timezone.utc)


class PreviousSnapshotGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.curated = json.loads((ROOT/'config/curated_issuer_facts.json').read_text())

    def snapshot(self, name, now=NOW):
        out = self.path/name
        build(ROOT/'seed/catalog-v2.db', out, curated=self.curated, clock=now)
        return out

    def test_one_removed_post_seed_link_is_blocked(self):
        old = self.snapshot('old')
        publication_decision(old, None, clock=NOW)
        new = self.snapshot('new', NOW+timedelta(days=1))
        path = new/'acceptance.json'
        rows = json.loads(path.read_text())
        index = next(i for i, row in enumerate(rows) if row['card_id']=='htzone-giftzone')
        rows.pop(index)
        raw = json.dumps(rows).encode(); path.write_bytes(raw)
        manifest = json.loads((new/'manifest.json').read_text())
        manifest['fileSha256']['acceptance.json'] = hashlib.sha256(raw).hexdigest()
        manifest['counts']['catalogCardMerchantLinks'] -= 1
        (new/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(SnapshotRegression, 'deleted card-merchants'):
            publication_decision(new, previous_from_dir(old), clock=NOW+timedelta(days=1))

    def test_corrupt_previous_snapshot_is_not_used_as_evidence(self):
        old = self.snapshot('old')
        (old/'cards.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            previous_from_dir(old)

    def test_unchanged_core_keeps_generated_at_during_offer_only_deployment(self):
        old = self.snapshot('old')
        publication_decision(old, None, clock=NOW)
        previous = previous_from_dir(old)
        new = self.snapshot('new', NOW+timedelta(days=1))
        result = publication_decision(new, previous, clock=NOW+timedelta(days=1))
        self.assertFalse(result['changed'])
        current = json.loads((new/'manifest.json').read_text())
        self.assertEqual(current['generatedAt'], previous[0]['generatedAt'])


if __name__ == '__main__':
    unittest.main()
