"""Attach ESPN-verified scheduled kickoff timestamps to Yahoo public games.

Match both teams, regardless of favorite or home/away, and only use unique ESPN
fixtures. Unknown fixtures have no kickoff rather than an invented time.
"""
import json
from build_predictions import DATA, fetch_results
from freeze_pregame import fixture_for

def run():
    for path in sorted(DATA.glob('week[0-9][0-9].json')):
        week = int(path.stem[4:])
        try:
            payload = json.loads(path.read_text())
            if not payload.get('games'):
                continue
            events = fetch_results(week)
        except (OSError, ValueError, KeyError) as exc:
            print(f'Week {week}: kickoff lookup unavailable ({exc})')
            continue
        matched = 0
        for game in payload['games']:
            fixture = fixture_for(game, events)
            if fixture:
                event_id, kickoff = fixture
                game['espn_event_id'] = event_id
                game['kickoff_utc'] = kickoff.isoformat()
                matched += 1
            else:
                game.pop('espn_event_id', None)
                game.pop('kickoff_utc', None)
        path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
        print(f'Week {week}: verified kickoff times for {matched}/{len(payload["games"])} games')

if __name__ == '__main__':
    run()
