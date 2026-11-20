"""Monitor upstream public GitHub changes without copying third-party catalog data.

Monitoring source activity does NOT imply redistribution rights or verified card
acceptance. This helper only prints the most recent commit hash/date for a file.
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WATCH = {
    'BUYME community index (license not established)':
        ('eladkishon', 'buyme-mcp', 'data/buyme.json'),
    'ClawSavings benefit data (MIT in README)':
        ('yhyatt', 'ClawSavings', 'discounts.json'),
}


def parse_commit(payload):
    if not isinstance(payload, list) or not payload:
        raise ValueError('GitHub API did not return any commits')
    item = payload[0]
    sha = item.get('sha')
    info = item.get('commit', {}).get('committer', {})
    updated = info.get('date')
    if not (isinstance(sha, str) and len(sha) == 40 and isinstance(updated, str)):
        raise ValueError('Unexpected GitHub commit API format')
    return {'commit': sha[:12], 'committedAt': updated}


def fetch_commit(owner, repository, filepath, token=None):
    args = urlencode({'path': filepath, 'per_page': 1})
    url = f'https://api.github.com/repos/{owner}/{repository}/commits?{args}'
    headers = {'Accept': 'application/vnd.github+json',
               'User-Agent': 'couponia-catalog-source-watcher/1.0',
               'X-GitHub-Api-Version': '2022-11-28'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        raw = response.read(200_001)
    if len(raw) > 200_000:
        raise ValueError('GitHub API response too large')
    return parse_commit(json.loads(raw))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--token-env', default='GITHUB_TOKEN',
                   help='Environment variable containing GitHub token (never printed)')
    args = p.parse_args()
    import os
    token = os.environ.get(args.token_env)
    for label, (owner, repo, filepath) in WATCH.items():
        info = fetch_commit(owner, repo, filepath, token)
        print(json.dumps({'source': label, 'file': f'{owner}/{repo}/{filepath}',
                          **info, 'importPlanned': label.startswith('ClawSavings')},
                         ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
