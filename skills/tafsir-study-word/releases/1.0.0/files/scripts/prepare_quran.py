"""Map the retained, verified Tanzil simple 1.1 source to surah:verse JSON.

The source is copied verbatim with its notice. Only an explicitly checked
opening basmala, joined to verse 1 by this source format, is separated.
This converter does not support arbitrary Quran formats or other verse counts.
"""
import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,
          98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,
          75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,
          13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,
          29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,8,3,
          9,5,4,7,3,6,3,5,4,5,6]


def letters(text):
    return ''.join(c for c in unicodedata.normalize('NFC', text)
                   if unicodedata.category(c).startswith('L') and c != 'ـ')


def prepare(source, metadata):
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != metadata['sha256']:
        raise ValueError('Quran source differs from the retained verified file; verify the new source and metadata explicitly')
    lines = [line.strip() for line in raw.decode('utf-8-sig').splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    if len(COUNTS) != 114 or sum(COUNTS) != 6236 or len(lines) != 6236:
        raise ValueError(f'Unexpected verse structure: {len(lines)} lines, {sum(COUNTS)} expected')
    result, i = {}, 0
    for surah, count in enumerate(COUNTS, 1):
        for verse in range(1, count + 1):
            text = lines[i]
            i += 1
            if verse == 1 and surah not in (1, 9):
                opening = re.match(r'^(?:\S+\s+){4}', text)
                if not opening or letters(opening.group()) != 'بسماللهالرحمنالرحيم':
                    raise ValueError(f'Missing or unexpected joined basmala at {surah}:1')
                text = text[opening.end():]
            if not text:
                raise ValueError(f'Empty verse {surah}:{verse}')
            result[f'{surah}:{verse}'] = text
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ASSETS / 'quran-simple-1.1.txt')
    parser.add_argument('--metadata', type=Path, default=ASSETS / 'quran-source.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding='utf-8-sig'))
    result = prepare(args.input, metadata)
    source_text = args.input.read_text(encoding='utf-8-sig')
    notice_start = source_text.find('# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK')
    if notice_start < 0:
        raise ValueError('The retained source copyright notice is missing')
    output = {'_meta': dict(metadata, copyright_notice=source_text[notice_start:]), **result}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'verses': len(result), 'source_sha256': metadata['sha256'], 'out': str(args.out.resolve())}))


if __name__ == '__main__':
    main()
