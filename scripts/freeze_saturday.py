"""Freeze a Saturday morning assessment separately from Thursday's public reference.

This does not alter Thursday records or claim a Thursday public spread is the
official locked line in a private Yahoo group. It captures only future games,
with current model projections compared to the earlier Thursday public line.
"""
import datetime as dt
import json
from zoneinfo import ZoneInfo
from build_predictions import DATA, YEAR, fetch_results, norm
from freeze_pregame import fixture_for

CENTRAL = ZoneInfo('America/Chicago')

def matchup(game):
    return tuple(sorted((norm(game['favorite']), norm(game['underdog']))))

def run():
    now = dt.datetime.now(dt.timezone.utc)
    local = now.astimezone(CENTRAL)
    if local.weekday() != 5 or local.hour < 8:
        print('Saturday snapshot: scheduled for after Saturday 8 AM Central')
        return
    folder = DATA / 'saturday'
    folder.mkdir(parents=True, exist_ok=True)
    for thursday in sorted((DATA / 'thursday').glob('week[0-9][0-9].json')):
        week = int(thursday.stem[4:])
        target = folder / thursday.name
        if target.exists():
            continue
        try:
            reference = json.loads(thursday.read_text())
            current = json.loads((DATA / f'week{week:02}.json').read_text())
            model = json.loads((DATA / f'week{week:02}_predictions.json').read_text())
            events = fetch_results(week)
        except (OSError, ValueError, KeyError) as exc:
            print(f'Saturday week {week}: data unavailable: {exc}')
            continue
        thursday_games = {x['espn_event_id']: x for x in reference.get('games', [])}
        predictions = {matchup(p): p for p in model.get('predictions', [])}
        assessments = []
        for game in current.get('games', []):
            matched = fixture_for(game, events)
            if not matched:
                continue
            event_id, kickoff = matched
            if event_id not in thursday_games or kickoff <= now:
                continue
            original = thursday_games[event_id]
            th_game = original['game']
            pick = predictions.get(matchup(game))
            if not pick:
                continue
            current_fav = norm(game['favorite'])
            original_fav = norm(th_game['favorite'])
            # Convert Thursday spread into Saturday's favorite perspective.
            th_spread = float(th_game['favorite_spread']) * (1 if current_fav == original_fav else -1)
            margin = float(pick['projected_favorite_margin'])
            edge_locked = margin + th_spread
            original_pick = original.get('prediction')
            assessments.append({
                'espn_event_id': event_id,
                'kickoff_utc': kickoff.isoformat(),
                'thursday_reference_game': th_game,
                'saturday_game': game,
                'thursday_pick': original_pick['recommended_team'] if original_pick else None,
                'saturday_pick': game['favorite'] if edge_locked > 0 else game['underdog'] if edge_locked < 0 else None,
                'saturday_projected_favorite_margin': round(margin, 2),
                'saturday_edge_vs_thursday_public_reference': round(edge_locked, 2),
                'pick_changed': bool(original_pick and original_pick['recommended_team'] != (game['favorite'] if edge_locked > 0 else game['underdog'] if edge_locked < 0 else None)),
                'note': 'Comparison of two public Yahoo snapshots, NOT an independently verified contest spread or market movement.',
            })
        if not assessments:
            print(f'Saturday week {week}: no upcoming matched games; no snapshot')
            continue
        target.write_text(json.dumps({
            'season': YEAR, 'week': week, 'captured_at': now.isoformat(),
            'captured_central': local.isoformat(),
            'source': 'Yahoo public line reference and current experimental model',
            'verified_official_contest_line': False,
            'games': assessments,
        }, indent=2) + '\n')
        print(f'Saturday week {week}: frozen {len(assessments)} remaining games, {sum(x["pick_changed"] for x in assessments)} changed picks')

if __name__ == '__main__':
    run()
