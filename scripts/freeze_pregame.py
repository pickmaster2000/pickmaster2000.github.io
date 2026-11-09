"""Freeze per-game pre-kickoff Yahoo spreads and model selections for forward testing.

Never creates historical 'pregame' records retrospectively. ESPN kickoff date
must be in the future and both teams must uniquely match the ESPN fixture.
Existing snapshots are immutable.
"""
import datetime as dt
import json
from pathlib import Path

from build_predictions import ALIASES, DATA, YEAR, fetch_results, names, norm


def team_keys(team):
    raw = names(team)
    return raw | {ALIASES.get(x, x) for x in raw}


def normalized(value):
    n = norm(value)
    return ALIASES.get(n, n)


def fixture_for(game, events):
    fav, dog = normalized(game['favorite']), normalized(game['underdog'])
    matching = []
    for event in events:
        try:
            comp = event['competitions'][0]
            entries = comp['competitors']
            if len(entries) != 2:
                continue
            first, second = entries
            teams = (team_keys(first['team']), team_keys(second['team']))
            if (fav in teams[0] and dog in teams[1]) or (fav in teams[1] and dog in teams[0]):
                kickoff = dt.datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                matching.append((str(event['id']), kickoff))
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    return matching[0] if len(matching) == 1 else None


def run():
    now = dt.datetime.now(dt.timezone.utc)
    out_dir = DATA / 'pregame'
    out_dir.mkdir(parents=True, exist_ok=True)
    for week in range(1, 15):
        try:
            slate = json.loads((DATA / f'week{week:02}.json').read_text())
            predictions = json.loads((DATA / f'week{week:02}_predictions.json').read_text())
            events = fetch_results(week)
        except (OSError, ValueError, KeyError) as exc:
            print(f'Pregame week {week}: skipped: {exc}')
            continue
        model = {(p['favorite'], p['underdog']): p for p in predictions.get('predictions', [])}
        entries = []
        for game in slate.get('games', []):
            fixture = fixture_for(game, events)
            if not fixture:
                continue
            event_id, kickoff = fixture
            if kickoff <= now:
                continue
            k = (game['favorite'], game['underdog'])
            if k not in model:
                continue
            path = out_dir / f'{event_id}.json'
            if path.exists():
                continue
            entries.append((path, {
                'season': YEAR, 'week': week, 'captured_at': now.isoformat(),
                'espn_event_id': event_id, 'kickoff_utc': kickoff.isoformat(),
                'game': game, 'prediction': model[k],
                'notice': 'Immutable first observed pre-kickoff snapshot; not a guarantee line equals official Yahoo contest line.',
            }))
        for path, payload in entries:
            path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
        if entries:
            print(f'Pregame week {week}: froze {len(entries)} future-event matchups')


if __name__ == '__main__':
    run()
