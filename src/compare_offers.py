"""Detect changes in offers payload without redeploying for manifest timestamp only.

Network failure treats previous feed as missing: this errs on the side of publishing
an updated, checked snapshot instead of keeping potentially stale offers online.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


def changed(local_manifest, previous_url):
    local = json.loads(Path(local_manifest).read_text(encoding='utf-8'))
    try:
        request = Request(previous_url, headers={'Accept':'application/json','User-Agent':'CouponiaOfferPublisher/1.0'})
        with urlopen(request, timeout=12) as response:
            if response.status != 200:
                return True
            raw = response.read(60_001)
            if len(raw) > 60_000:
                return True
            old = json.loads(raw)
        return old['fileSha256']['offers.json'] != local['fileSha256']['offers.json']
    except (OSError, ValueError, KeyError, TypeError):
        return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--local', required=True)
    p.add_argument('--previous-url', required=True)
    args = p.parse_args()
    value = 'true' if changed(args.local, args.previous_url) else 'false'
    print('Offers changed: ' + value)
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f:
            f.write('changed=' + value + '\n')

if __name__ == '__main__':
    main()
