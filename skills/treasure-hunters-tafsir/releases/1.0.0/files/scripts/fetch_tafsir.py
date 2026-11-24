"""Fetch complete Saadi source pages, keeping raw HTML and extraction provenance."""
import argparse
import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from lxml import html

def extract(raw):
    root = html.fromstring(raw)
    full = root.text_content()
    title=' '.join(root.xpath('//title/text()'))
    if 'السعدي' not in title or 'تيسير الكريم الرحمن' not in full:
        raise ValueError('Page does not identify the expected Saadi book')
    divs = root.xpath('//article[contains(@class,"verse-block")]//div[contains(concat(" ",normalize-space(@class)," ")," prose ")]')
    if not divs:
        raise ValueError('No tafsir content blocks found; inspect raw HTML rather than returning empty text')
    blocks = []
    for div in divs:
        for foot in div.xpath('.//div[contains(@class,"foot-notes")]'): foot.drop_tree()
        for br in div.xpath('.//br'): br.tail = '\n' + (br.tail or '')
        text = re.sub(r'-\[[٠-٩0-9]+\]-', '', div.text_content())
        text = re.sub(r'\([٠-٩]+\)', '', text)
        lines = [re.sub(r'[ \t\r]+', ' ', line).strip() for line in text.split('\n') if line.strip()]
        if lines: blocks.append(lines)
    if sum(len(' '.join(b)) for b in blocks) < 40:
        raise ValueError('Suspiciously short extraction')
    return blocks

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--surahs', nargs='+', type=int, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--input-dir', type=Path, help='Read source{N}.html snapshots instead of network')
    args = parser.parse_args()
    if any(not 1 <= n <= 114 for n in args.surahs): parser.error('Surahs must be 1..114')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for n in dict.fromkeys(args.surahs):
        url = f'https://quranpedia.net/surah/1/{n}/book/3'
        if args.input_dir:
            raw = (args.input_dir / f'source{n}.html').read_bytes()
        else:
            for attempt in range(2):
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=30) as response: raw = response.read()
                    break
                except Exception:
                    if attempt: raise
                    time.sleep(1)
        raw_path = args.output_dir / f'source{n}.html'
        raw_path.write_bytes(raw)
        data = {'chapter': n, 'url': url, 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                'sha256': hashlib.sha256(raw).hexdigest(), 'raw_file': raw_path.name,
                'blocks': extract(raw),
                'review_required': 'Cards may split author passages; verify ranges, Quran quotations, and trailing next-surah headings.'}
        (args.output_dir / f'source{n}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'{n}: {len(data["blocks"])} extracted source blocks')

if __name__ == '__main__': main()
