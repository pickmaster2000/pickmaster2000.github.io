"""Score only immutable snapshots captured before kickoff.

This is a forward-tracked record; no later model changes or lines are substituted.
"""
import datetime as dt
import json

from build_predictions import DATA, YEAR, fetch_results

def run():
    snapshots = sorted((DATA / 'pregame').glob('*.json'))
    totals = {'wins': 0, 'losses': 0, 'pushes': 0, 'pending': 0, 'unmatched': 0}
    weeks = {}
    by_signal = {'watchlist': {'wins': 0, 'losses': 0, 'pushes': 0}, 'weak_lean': {'wins': 0, 'losses': 0, 'pushes': 0}}
    baselines = {'always_favorite': {'wins': 0, 'losses': 0, 'pushes': 0}, 'always_underdog': {'wins': 0, 'losses': 0, 'pushes': 0}}
    events = {}
    for path in snapshots:
        try:
            record = json.loads(path.read_text())
            week = int(record['week'])
            kickoff = dt.datetime.fromisoformat(record['kickoff_utc'])
            recorded = dt.datetime.fromisoformat(record['captured_at'])
            if recorded >= kickoff:
                totals['unmatched'] += 1
                continue
            if week not in events:
                events[week] = {str(x['id']): x for x in fetch_results(week)}
            event = events[week].get(str(record['espn_event_id']))
            if not event:
                totals['unmatched'] += 1
                continue
            competition = event['competitions'][0]
            status = competition.get('status') or event.get('status') or {}
            if not status.get('type', {}).get('completed'):
                totals['pending'] += 1
                continue
            participants = competition['competitors']
            if len(participants) != 2:
                totals['unmatched'] += 1
                continue
            # Use the immutable ESPN event ID and ESPN's 'homeAway' flags.
            from build_predictions import ALIASES, names, norm
            def key(n):
                k = norm(n)
                return ALIASES.get(k, k)
            fav = key(record['game']['favorite'])
            dog = key(record['game']['underdog'])
            by_team = {}
            for p in participants:
                variations = names(p['team'])
                variations |= {ALIASES.get(v,v) for v in variations}
                for n in (fav, dog):
                    if n in variations:
                        by_team[n] = float(p['score'])
            if len(by_team) != 2:
                totals['unmatched'] += 1
                continue
            fav_cover = by_team[fav] - by_team[dog] + float(record['game']['favorite_spread'])
            if abs(fav_cover) < 0.01:
                result = 'pushes'
            else:
                selected_favorite = record['prediction']['recommended_team'] == record['game']['favorite']
                result = 'wins' if (fav_cover > 0) == selected_favorite else 'losses'
            totals[result] += 1
            signal = record['prediction'].get('signal', 'weak_lean')
            by_signal.setdefault(signal, {'wins': 0, 'losses': 0, 'pushes': 0})[result] += 1
            fv = 'pushes' if abs(fav_cover) < .01 else ('wins' if fav_cover > 0 else 'losses')
            dg = 'pushes' if abs(fav_cover) < .01 else ('wins' if fav_cover < 0 else 'losses')
            baselines['always_favorite'][fv] += 1
            baselines['always_underdog'][dg] += 1
            summary = weeks.setdefault(str(week), {'wins': 0, 'losses': 0, 'pushes': 0})
            summary[result] += 1
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            totals['unmatched'] += 1
            print(f'Prospective audit skipped {path.name}: {exc}')
    decided = totals['wins'] + totals['losses']
    output = {
        'season': YEAR,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'method': 'First-captured pre-kickoff Yahoo public spread and contemporaneous model pick, scored using final ESPN results',
        'notice': 'Forward-tracked evidence, NOT a claim of profitable performance. Public Yahoo lines may differ from private contest lines. Low sample sizes are unreliable.',
        'total': {**totals, 'win_pct_excluding_pushes': round(100 * totals['wins']/decided,1) if decided else None},
        'weeks': weeks,
        'by_signal': by_signal,
        'same_games_baselines': baselines,
    }
    (DATA / 'prospective.json').write_text(json.dumps(output, indent=2) + '\n')
    print(f'Prospective audit: {totals}')


if __name__ == '__main__':
    run()
