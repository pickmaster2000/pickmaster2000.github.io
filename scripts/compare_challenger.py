"""Side-by-side audit of challenger and incumbent on IDENTICAL historical games.

Results are exploratory. Yahoo spreads may have been retrieved after kickoff.
No model is promoted by this script, and no tuning takes place here.
"""
import datetime as dt
import json
from build_predictions import DATA, YEAR, extract, fetch_results
from backtest import classify

def blank():
    return {'wins': 0, 'losses': 0, 'pushes': 0}

def update(outcome, chose_fav, cover):
    result = 'pushes' if abs(cover) < 0.01 else 'wins' if ((cover > 0) == chose_fav) else 'losses'
    outcome[result] += 1

def run():
    outcomes = {x: blank() for x in ('incumbent', 'challenger', 'always_favorite', 'always_underdog')}
    weeks = []
    for path in sorted((DATA/'challenger').glob('week[0-9][0-9].json')):
        week = int(path.name[4:6])
        try:
            incumbent = json.loads((DATA/f'week{week:02}_predictions.json').read_text())
            challenger = json.loads(path.read_text())
            slate = json.loads((DATA/f'week{week:02}.json').read_text())
            events = extract(fetch_results(week), dt.datetime(YEAR+1, 1, 1, tzinfo=dt.timezone.utc))
        except (OSError, KeyError, ValueError) as exc:
            print(f'Compare week {week}: unavailable ({exc})')
            continue
        old = {(x['favorite'],x['underdog']):x for x in incumbent['predictions']}
        new = {(x['favorite'],x['underdog']):x for x in challenger['predictions']}
        games = {(x['favorite'],x['underdog']):x for x in slate['games']}
        cnt = 0
        for key in sorted(set(old)&set(new)&set(games)):
            game = games[key]
            actual = classify(old[key], events)
            if actual is None:
                continue
            cover = actual + float(game['favorite_spread'])
            update(outcomes['incumbent'], old[key]['recommended_team'] == game['favorite'], cover)
            update(outcomes['challenger'], new[key]['recommended_team'] == game['favorite'], cover)
            update(outcomes['always_favorite'], True, cover)
            update(outcomes['always_underdog'], False, cover)
            cnt += 1
        weeks.append({'week': week, 'same_games_evaluated': cnt})
        print(f'Compare week {week}: {cnt} games with both models and final scores')
    for record in outcomes.values():
        decided = record['wins']+record['losses']
        record['win_pct_excluding_pushes'] = round(100*record['wins']/decided,1) if decided else None
        record['evaluated'] = decided+record['pushes']
    result = {
        'season': YEAR, 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'status': 'RETROSPECTIVE EXPLORATORY COMPARISON: NOT a real-time pregame backtest. This does not establish profitable predictive accuracy.',
        'limitation': 'Historical Yahoo slate spreads may have been refreshed after kickoff; incumbent backfills may also reflect later model-code changes.',
        'models': outcomes, 'weeks': weeks,
        'decision': 'Challenger remains separate; do not replace production until independently verified prospective results warrant it.',
    }
    (DATA/'challenger_comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Comparison:', json.dumps(outcomes))

if __name__ == '__main__':
    run()
