"""Warn when manually reviewed issuer associations need a fresh source check.

This does not scrape websites, create new POS claims or modify catalog versions.
"""
import argparse
import json
from datetime import date
from pathlib import Path


def overdue_cards(payload, today=None, max_age_days=60):
    today = today or date.today()
    results = []
    for section, key in (('cards','id'),('existingCards','cardId'),('productReviews','cardId')):
        for item in payload.get(section, []):
            age = (today - date.fromisoformat(item['observedAt'][:10])).days
            if age >= max_age_days:
                results.append((item[key], age, item['sourceUrl']))
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--curated-file', default='config/curated_issuer_facts.json')
    p.add_argument('--max-age-days', type=int, default=60)
    a = p.parse_args()
    data = json.loads(Path(a.curated_file).read_text(encoding='utf8'))
    due = overdue_cards(data, max_age_days=a.max_age_days)
    if not due:
        print('Issuer review status: current within configured review window')
    for card, age, url in due:
        print(f'::warning::Issuer recheck due: {card} last reviewed {age} days ago; {url}')
    total = sum(len(data.get(section, [])) for section in ('cards','existingCards','productReviews'))
    print(f'Issuer review status: {len(due)} of {total} products require recheck')


if __name__ == '__main__':
    main()
