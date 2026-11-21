# Couponia Catalog v3.4 - additive issuer evidence and safe offer groundwork

Date: 2026-11-21. This is a **cumulative overlay** containing the previous
v3.2/v3.3 modifications. Copy onto the existing `couponia-catalog` repository.
It is **not a standalone repository**; keep the existing `seed/catalog-v2.db`,
`src/release.py`, `src/watch_sources.py`, and all unrelated project files.

## Local results, not yet deployed

| Metric | v3.3 local preview | v3.4 local preview | Delta |
|---|---:|---:|---:|
| Gift-card products | 107 | 108 | +1 |
| Distinct merchants | 445 | 462 | +17 |
| Card-to-merchant relationships | 606 | 648 | +42 |

The preview seed was reconstructed from the supplied Couponia Android catalog
assets (99 products, 409 merchants, 504 links), because the original full GitHub
repository seed is not part of the provided update ZIP. Real GitHub Actions
counts must be checked after applying this overlay; a different seed/alias set
can change distinct merchant counts.

### New issuer-reviewed, product-specific evidence

- `htzone-giftzone` (**new product**): 23 selected merchant relationships from
  `https://www.htzone.co.il/voucher-zone/4`. Examples: Castro, GOLF,
  book stores, adidas, JanSport, Swarovski, and Mega Sport. Retailer-specific
  restrictions are stored; online-only JanSport and selected-branch Swarovski
  are deliberately not represented as generic nationwide in-store acceptance.
- `buyme-baby` (**existing product, previously zero links**): +8 selected
  relationships from `https://buyme.co.il/brands/9018727`.
- `buyme-brunch` (**existing product, previously zero links**): +4 selected
  relationships from `https://buyme.co.il/brands/17573615`. The Cafe Greg
  record is scoped to **selected branches**, not the entire chain.
- `buyme-local` (**existing product, previously zero links**): +7 selected
  relationships from `https://buyme.co.il/brands/17573670`.
- `swish-plus`: the stored product URL and cautionary note now point to the
  precise issuer product page:
  `https://swish.co.il/home/all-gifts-giftcard/product-105984`.
  **No Swish Plus merchant relationships were invented** because a
  product-specific, stable merchant roster could not be verified.

These are deliberately **small manual observations**, not an automatic copy
of any issuer's complete merchant database. An issuer listing means `listed`,
**not** proven checkout acceptance. Individual outlets, channels, expiration,
and issuer terms can change.

## Code and safety changes

1. `src/curation.py`: accepts optional `existingCards` to append exact evidence
   to a seed card. Requires an exact existing ID, matching issuer and product
   name, and scoped source URL. Preserves existing card-to-merchant links,
   rejects conflicting aliases, validates channel/scope and never deletes.
2. `productReviews`: supports product-page evidence **without** adding any
   acceptance association (used for Swish Plus).
3. `src/catalog_guard.py`: checks that the rebuilt catalog preserves all
   baseline card and merchant identities and baseline relationships. Optional
   `--previous-db` checks against a previously downloaded published database.
   The GitHub Action automatically runs the baseline guard before deployment.
4. `src/review_status.py`: the 60-day manual issuer review reminder now includes
   existing-card review records and product-only reviews as well as new cards.
5. Android v3 compatibility: no change to schemaVersion (3), four files used
   by Android, manifest checksum contract or existing feed URL.
6. `src/offer_contract.py` and `config/offer_source_registry.json`:
   groundwork for a **future** credit-card/club benefits feature. Six official
   source records are **disabled** and no automated scraping or offer import is
   activated. A future offer may only be labelled publishable with explicit
   product eligibility, a current validity window, availability, issuer
   verification, a recent check and redistribution rights.
7. `config/source_registry_research.json`: the 18 research sources from the
   previous audit, all disabled and with rights caveats.

## Installation

1. Open the existing `Shay-M/couponia-catalog` in GitHub Desktop on `master`.
2. Back up or commit uncommitted local changes first. Extract the **full**
   `Couponia_Catalog_v3_4_GitHub_Update.zip` at the repository root, including
   the hidden `.github` directory. Do **not** erase unmentioned files.
3. Run the full tests in the repository:

   ```bash
   python -m unittest discover -s tests -v
   python src/build.py --seed seed/catalog-v2.db --curated-file config/curated_issuer_facts.json --out dist/v3
   python src/catalog_guard.py --seed seed/catalog-v2.db --catalog dist/v3/catalog.db
   python -m src.review_status --curated-file config/curated_issuer_facts.json
   ```

4. Check the diff in GitHub Desktop; commit and push to `master`.
5. Under GitHub Actions run `Build unified Israeli gift-card catalog`. Check
   the tests, catalog guard, build and `Compare with last published catalog`.
6. Verify the published manifest at
   `https://shay-m.github.io/couponia-catalog/v3/manifest.json` and then
   choose **Check for updates now** in Couponia's catalog settings.

**No Android APK update is required** for this catalog-only stage.

## Verification boundaries

The provided overlay lacks the live repository's `src/release.py` and other
existing tests. Locally, 20 tests completed successfully and 2 release-specific
tests were skipped because that file was unavailable. The release diff checks
and the remainder of the repository tests must run in your full GitHub checkout.
Nothing has been pushed or published from this environment.

## Explicitly deferred

- Wholesale reuse of other developers' scanned BUYME/HTZone/Swish datasets;
  a public GitHub repository is not a data-redistribution licence.
- Retailer links for Swish Plus that lack reliable, exact-product evidence.
- Live credit-card offers, credit-card-number storage, user eligibility checks,
  coupon stock state or expiry-sensitive claims in the Android UI.
- Automatic removal of old listings based solely on changes to third-party
  pages; verify issuer evidence and operator approval first.
