"""Save a Thursday-evening reference slate without rewriting prior snapshots.

Yahoo states normal-week official contest spreads use Thursday's line, but
does not publish a guaranteed exact lock *time*. The public distribution
is not necessarily identical to a private group's official spread.
Capture after 6 p.m. America/Chicago Thursdays, only when the upcoming
slate has uniquely matched future ESPN games within nine days.
"""
import datetime as dt
import json
from zoneinfo import ZoneInfo

from build_predictions import DATA, YEAR, fetch_results
from freeze_pregame import fixture_for

LOCAL = ZoneInfo('America/Chicago')
START_HOUR = 18


def run():
    now = dt.datetime.now(dt.timezone.utc)
    central = now.astimezone(LOCAL)
    if central.weekday() != 3 or central.hour < START_HOUR:
        print('Thursday snapshot: only eligible after Thursday 6 PM Central')
        return
    folder = DATA / 'thursday'
    folder.mkdir(parents=True, exist_ok=True)
    for week in range(1, 15):
        target = folder / f'week{week:02}.json'
        if target.exists():
            continue
        try:
            slate = json.loads((DATA / f'week{week:02}.json').read_text())
            predictions = json.loads((DATA / f'week{week:02}_predictions.json').read_text())
            events = fetch_results(week)
        except (OSError, ValueError, KeyError) as exc:
            print(f'Thursday week {week}: skipped: {exc}')
            continue
        model = {(p['favorite'], p['underdog']): p for p in predictions.get('predictions', [])}
        games = []
        for game in slate.get('games', []):
            fixture = fixture_for(game, events)
            if not fixture:
                continue
            event_id, kickoff = fixture
            if not now < kickoff < now + dt.timedelta(days=9):
                continue
            # Games are included only with an independently matched ESPN event.
            pick = model.get((game['favorite'], game['underdog']))
            games.append({
                'espn_event_id': event_id,
                'kickoff_utc': kickoff.isoformat(),
                'game': game,
                'prediction': pick,
            })
        # Guard against saving an unrelated or incomplete week.
        if len(games) < 10:
            print(f'Thursday week {week}: only {len(games)} upcoming matched fixtures, no snapshot')
            continue
        payload = {
            'week': week, 'season': YEAR,
            'captured_at': now.isoformat(),
            'captured_central': central.isoformat(),
            'source': 'Yahoo PUBLIC spread distribution',
            'verified_official_contest_line': False,
            'note': 'Thursday-evening public reference, NOT a verified private-group lock or independent sportsbook market line.',
            'games': games,
        }
        target.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
        print(f'Thursday week {week}: froze {len(games)} games')

if __name__ == '__main__':
    run()
