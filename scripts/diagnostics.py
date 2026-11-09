"""Diagnostic slices of retrospective ATS model performance.

Yahoo public snapshots may have changed after kickoff. These are exploratory
statistics, not immutable pregame line backtests or evidence of an edge.
"""
import datetime as dt
import json
from build_predictions import DATA, YEAR, extract, fetch_results
from backtest import classify

CATEGORIES = (
    'all', 'favorite', 'underdog', 'home', 'away', 'neutral_or_unknown',
    'baseline_always_favorite', 'baseline_always_underdog',
    'watchlist', 'weak_lean',
    'spread_under_7', 'spread_7_to_14', 'spread_over_14',
    'with_public_majority', 'against_public_majority', 'public_tied_or_unknown',
)

def empty():
    return {'wins': 0, 'losses': 0, 'pushes': 0, 'count': 0}

def add(record, verdict):
    record['count'] += 1
    record[verdict] += 1

def summary(record):
    decided = record['wins'] + record['losses']
    return {**record, 'win_pct_excluding_pushes': round(100 * record['wins'] / decided, 1) if decided else None}

def run():
    groups = {name: empty() for name in CATEGORIES}
    weekly = []
    for path in sorted(DATA.glob('week[0-9][0-9]_predictions.json')):
        week = int(path.name[4:6])
        if week < 4:
            continue
        try:
            snapshot = json.loads((DATA / f'week{week:02}.json').read_text())
            predictions = json.loads(path.read_text())['predictions']
            events = fetch_results(week)
        except (OSError, ValueError, KeyError) as exc:
            print(f'Week {week}: diagnostic unavailable: {exc}')
            continue
        finished = extract(events, dt.datetime(YEAR+1, 1, 1, tzinfo=dt.timezone.utc))
        if not finished:
            continue
        slate = {(g['favorite'], g['underdog']): g for g in snapshot['games']}
        week_count = 0
        for prediction in predictions:
            game = slate.get((prediction['favorite'], prediction['underdog']))
            if game is None:
                continue
            actual = classify(prediction, finished)
            if actual is None:
                continue
            cover = actual + float(game['favorite_spread'])
            chose_fav = prediction['recommended_team'] == game['favorite']
            verdict = 'pushes' if abs(cover) < .01 else ('wins' if ((cover > 0) == chose_fav) else 'losses')
            used = ['all', 'favorite' if chose_fav else 'underdog']
            pick_home = game['favorite_home'] if chose_fav else game['underdog_home']
            if game['favorite_home'] == game['underdog_home']:
                used.append('neutral_or_unknown')
            else:
                used.append('home' if pick_home else 'away')
            used.append('watchlist' if prediction.get('signal') == 'watchlist' else 'weak_lean')
            spread = abs(float(game['favorite_spread']))
            used.append('spread_under_7' if spread < 7 else 'spread_7_to_14' if spread <= 14 else 'spread_over_14')
            pct = game['favorite_pick_pct'] if chose_fav else game['underdog_pick_pct']
            used.append('with_public_majority' if pct > 50 else 'against_public_majority' if pct < 50 else 'public_tied_or_unknown')
            # Compare on precisely the same games, avoiding misleading baselines.
            baseline_fav = 'pushes' if abs(cover) < .01 else ('wins' if cover > 0 else 'losses')
            baseline_dog = 'pushes' if abs(cover) < .01 else ('wins' if cover < 0 else 'losses')
            add(groups['baseline_always_favorite'], baseline_fav)
            add(groups['baseline_always_underdog'], baseline_dog)
            for name in used:
                add(groups[name], verdict)
            week_count += 1
        weekly.append({'week': week, 'evaluated': week_count})
    payload = {
        'season': YEAR,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'warning': 'Exploratory retrospective slices; Yahoo spreads may have changed after kickoff. Baselines use exactly the same matched games. Do not optimize parameters or claim predictive advantage from these samples.',
        'groups': {name: summary(record) for name, record in groups.items()},
        'weeks': weekly,
    }
    (DATA / 'diagnostics.json').write_text(json.dumps(payload, indent=2) + '\n')
    for name, values in payload['groups'].items():
        print(f"{name}: {values['wins']}-{values['losses']}-{values['pushes']} ({values['win_pct_excluding_pushes']}%)")

if __name__ == '__main__':
    run()
