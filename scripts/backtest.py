"""Retrospective ATS audit using prior-week-only ratings and public Yahoo spreads.

Not a true point-in-time backtest: public Yahoo spreads and pick percentages may
have been refreshed after kickoff. This report is an exploratory diagnostic.
"""
import datetime as dt
import json
import pathlib

from build_predictions import ALIASES, DATA, YEAR, extract, fetch_results, names, norm

MIN_WEEK = 4


def aliases(team):
    out = set()
    for item in names(team):
        out.add(item)
        out.add(ALIASES.get(item, item))
    return out


def key_name(value):
    n = norm(value)
    return ALIASES.get(n, n)


def classify(prediction, events):
    favorite, underdog = key_name(prediction['favorite']), key_name(prediction['underdog'])
    matched = []
    for _, event_id, home, away, _ in events:
        home_names = aliases(home['team'])
        away_names = aliases(away['team'])
        if favorite in home_names and underdog in away_names:
            margin = float(home['score']) - float(away['score'])
            matched.append((event_id, margin))
        elif favorite in away_names and underdog in home_names:
            margin = float(away['score']) - float(home['score'])
            matched.append((event_id, margin))
    if len(matched) != 1:
        return None
    return matched[0][1]


def run():
    audits = []
    total = {'wins': 0, 'losses': 0, 'pushes': 0, 'unmatched': 0, 'evaluated': 0}
    weeks = sorted(DATA.glob('week[0-9][0-9]_predictions.json'))
    for path in weeks:
        week = int(path.name[4:6])
        if week < MIN_WEEK:
            continue
        try:
            snapshot = json.loads((DATA / f'week{week:02}.json').read_text())
            model = json.loads(path.read_text())
            events = fetch_results(week)
        except (OSError, ValueError, KeyError) as exc:
            print(f'Backtest week {week}: no usable records ({exc})')
            continue
        cutoff = dt.datetime(YEAR + 1, 1, 1, tzinfo=dt.timezone.utc)
        completed = extract(events, cutoff)
        if not completed:
            print(f'Backtest week {week}: no completed games; skipping')
            continue
        slate = {(g['favorite'], g['underdog']): g for g in snapshot['games']}
        summary = {'week': week, 'wins': 0, 'losses': 0, 'pushes': 0, 'unmatched': 0, 'evaluated': 0, 'slate_games': len(snapshot['games']), 'model_picks': len(model.get('predictions', []))}
        for prediction in model.get('predictions', []):
            k = (prediction['favorite'], prediction['underdog'])
            game = slate.get(k)
            if not game:
                continue
            actual = classify(prediction, completed)
            if actual is None:
                summary['unmatched'] += 1
                continue
            cover_margin = actual + float(game['favorite_spread'])
            if abs(cover_margin) < 0.01:
                summary['pushes'] += 1
            elif (cover_margin > 0) == (prediction['recommended_team'] == prediction['favorite']):
                summary['wins'] += 1
            else:
                summary['losses'] += 1
            summary['evaluated'] += 1
        for key in total:
            total[key] += summary[key]
        audits.append(summary)
        print(f"Backtest week {week}: W {summary['wins']} L {summary['losses']} P {summary['pushes']}, unmatched {summary['unmatched']}")
    decided = total['wins'] + total['losses']
    payload = {
        'season': YEAR,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'method': 'Retrospective, prior-week-only model against available ESPN final scores and current public Yahoo snapshot spreads',
        'limitations': [
            'NOT a true point-in-time historical backtest. Yahoo snapshots may have been retrieved or updated after games occurred.',
            'ATS spreads from the public Yahoo distribution may differ from the user\'s contest lines and closing market odds.',
            'No claims about profitable performance, injury/weather adjustments, or statistically calibrated probabilities.',
            'Only games with a model pick and a unique ESPN final-score match are evaluated; small or missing samples may bias results.',
        ],
        'total': {**total, 'win_rate_excluding_pushes': round(100 * total['wins'] / decided, 1) if decided else None},
        'weeks': audits,
    }
    (DATA / 'backtest.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(f'Backtest audit saved: {total}')


if __name__ == '__main__':
    run()
