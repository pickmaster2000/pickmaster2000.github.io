"""Fetch Yahoo public College Football Pick Distribution; reject malformed matchups.
No paid API required. Uses Python standard library only.
"""
import datetime
import json
import os
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = 'https://football.fantasysports.yahoo.com/college/pickdistribution?type=sc&week={}'
ROOT = Path(__file__).resolve().parents[1]
DATE = re.compile(r'^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*,?\s+\w+\s+\d+', re.I)
SPREAD_SUFFIX = re.compile(r'\s*\(\s*[+-]?\d+(?:\.\d+)?\s*pts\s*\)\s*$', re.I)
POINTS = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*pts\s*$', re.I)

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('td', 'th', 'tr', 'div', 'p', 'h3', 'h4', 'li', 'br'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        if tag in ('td', 'th', 'tr', 'div', 'p', 'h3', 'h4', 'li'):
            self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

def clean_team(value):
    value = SPREAD_SUFFIX.sub('', value).strip()
    home = value.startswith('@')
    value = value.lstrip('@ ').strip()
    if not value or DATE.match(value) or re.search(r'\b(?:EST|EDT|CST|CDT|PST|PDT)\b', value):
        return None
    if value in ('Favorite', 'Underdog', 'Record', 'Avg. Confidence') or len(value) > 65:
        return None
    if re.search(r'\d{1,2}:\d{2}\s*(?:am|pm)', value, re.I):
        return None
    return value, home

def parse(html):
    parser = TextParser()
    parser.feed(html)
    lines = [re.sub(r'\s+', ' ', x).strip() for x in ''.join(parser.parts).splitlines()]
    lines = [x for x in lines if x]
    games = []
    seen = set()
    for i, line in enumerate(lines):
        if line != 'Favorite':
            continue
        # Stop at the next game marker rather than borrowing fields from another game.
        stop = next((j for j in range(i + 1, min(i + 45, len(lines))) if lines[j] == 'Favorite'), min(i + 45, len(lines)))
        segment = lines[i:stop]
        try:
            fi = segment.index('Favorite Pick Percentage')
            ui = segment.index('Underdog')
            pi = segment.index('Underdog Pick Percentage')
            if not (1 < fi < ui < pi):
                continue
            favorite = clean_team(segment[1])
            underdog = clean_team(segment[ui + 1])
            if not favorite or not underdog or favorite[0] == underdog[0]:
                continue
            fp_match = re.fullmatch(r'(\d{1,3})\s*%', segment[fi + 1])
            up_match = re.fullmatch(r'(\d{1,3})\s*%', segment[pi + 1])
            if not fp_match or not up_match:
                continue
            fp, up = int(fp_match.group(1)), int(up_match.group(1))
            if not (0 <= fp <= 100 and 0 <= up <= 100):
                continue
            if fp + up != 0 and abs(fp + up - 100) > 2:
                continue
            spreads = [float(m.group(1)) for t in segment[pi + 2:] if (m := POINTS.fullmatch(t))]
            if not spreads:
                continue
            spread = spreads[0]
            if not 0 < spread <= 70:
                continue
            key = tuple(sorted((favorite[0].casefold(), underdog[0].casefold())))
            if key in seen:
                continue
            seen.add(key)
            games.append({
                'favorite': favorite[0], 'underdog': underdog[0],
                'favorite_home': favorite[1], 'underdog_home': underdog[1],
                'favorite_spread': -spread,
                'favorite_pick_pct': fp, 'underdog_pick_pct': up,
            })
        except (ValueError, IndexError, AttributeError):
            continue
    return games

def main():
    week = int(os.getenv('WEEK', '0') or 0)
    weeks = [week] if 1 <= week <= 14 else range(1, 15)
    data_dir = ROOT / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    for w in weeks:
        url = BASE.format(w)
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; Pickmaster2000/1.0; personal project)',
                'Accept': 'text/html',
            })
            with urllib.request.urlopen(req, timeout=18) as response:
                html = response.read().decode('utf-8', 'replace')
            games = parse(html)
            if not games:
                print(f'Week {w}: no verified games parsed; keeping prior valid snapshot')
                continue
            payload = {
                'week': w,
                'source': 'Yahoo public Pick Distribution (Spread and Confidence)',
                'source_url': url,
                'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'games': games,
                'note': 'Public pick percentages are not ATS probabilities. Public games may differ from your Yahoo group.',
            }
            (data_dir / f'week{w:02}.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
            print(f'Week {w}: saved {len(games)} verified games')
        except Exception as error:
            print(f'Week {w}: request failed ({type(error).__name__}: {error}); keeping prior valid snapshot')

if __name__ == '__main__':
    main()
