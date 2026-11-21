"""Contract: registry entries are research targets, not permitted offer feeds."""
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

class OfferSourceRegistryTests(unittest.TestCase):
    def test_only_explicit_official_https_urls_and_no_enabled_imports(self):
        path = Path(__file__).resolve().parents[1] / "config/offer_source_registry.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources=payload["sources"]
        self.assertEqual(8, len(sources))
        self.assertEqual(len(sources), len({source["id"] for source in sources}))
        for source in sources:
            url = urlsplit(source["url"])
            self.assertEqual("https",url.scheme)
            self.assertTrue(url.hostname)
            self.assertFalse(source["enabled"])
            self.assertEqual("not_verified", source["rightsStatus"])
            self.assertEqual("discovery_only", source["dataPurpose"])

if __name__ == "__main__": unittest.main()
