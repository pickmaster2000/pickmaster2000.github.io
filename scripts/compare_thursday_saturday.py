"""Compare Thursday and Saturday frozen picks on identical completed games.

Only grades games present in BOTH immutable captures. Uses the Thursday PUBLIC
reference spread, not an asserted official Yahoo private-group contest line.
"""
import datetime as dt
import json

from build_predictions import DATA, YEAR, fetch_results, ALIASES, names, norm

def canonical(s):
    n = norm(s)
    return ALIASES.get(n, n)

def outcome(event, favorite, underdog, spread):
    participants = event['competitions'][0]['competitors']
    if len(participants) != 2:
        return None
    scores = {}
    for entry in participants:
        keys = names(entry['team'])
        keys |= {ALIASES.get(k, k) for k in keys}
        for name in (favorite, underdog):
            if name in keys:
                scores[name] = float(entry['score'])
    if len(scores) != 2:
        return None
    return scores[favorite] - scores[underdog] + spread

def grade(pick, favorite, underdog, cover):
    if not pick:
        return None
    if abs(cover) < 0.01:
        return 'pushes'
    if canonical(pick) == favorite:
        return 'wins' if cover > 0 else 'losses'
    if canonical(pick) == underdog:
        return 'wins' if cover < 0 else 'losses'
    return None

def record():
    return {'wins': 0, 'losses': 0, 'pushes': 0}

def run():
    totals = {'thursday': record(), 'saturday': record(), 'changed_picks': 0, 'completed_games': 0, 'pending': 0, 'unmatched': 0}
    details = []
    for path in sorted((DATA / 'saturday').glob('week[0-9][0-9].json')):
        try:
            saturday = json.loads(path.read_text())
            week = int(saturday['week'])
            thursday = json.loads((DATA / 'thursday' / path.name).read_text())
            th = {e['espn_event_id']: e for e in thursday['games']}
            events = {str(e['id']): e for e in fetch_results(week)}
        except (OSError, KeyError, ValueError) as exc:
            print(f'Week comparison unavailable: {exc}')
            continue
        for item in saturday['games']:
            event_id = item['espn_event_id']
            original = th.get(event_id)
            event = events.get(event_id)
            if not original or not event:
                totals['unmatched'] += 1
                continue
            try:
                game = original['game']
                favorite, underdog = canonical(game['favorite']), canonical(game['underdog'])
                if len({favorite, underdog}) != 2:
                    totals['unmatched'] += 1
                    continue
                status = event['competitions'][0].get('status') or event.get('status') or {}
                if not status.get('type', {}).get('completed'):
                    totals['pending'] += 1
                    continue
                cover = outcome(event, favorite, underdog, float(game['favorite_spread']))
                if cover is None:
                    totals['unmatched'] += 1
                    continue
                t_pick = item.get('thursday_pick')
                s_pick = item.get('saturday_pick')
                t = grade(t_pick, favorite, underdog, cover)
                s = grade(s_pick, favorite, underdog, cover)
                if not t or not s:
                    totals['unmatched'] += 1
                    continue
                totals['thursday'][t] += 1
                totals['saturday'][s] += 1
                totals['completed_games'] += 1
                changed = canonical(t_pick) != canonical(s_pick)
                totals['changed_picks'] += int(changed)
                details.append({'week': week, 'espn_event_id': event_id, 'thursday_result': t, 'saturday_result': s, 'changed': changed})
            except (KeyError, ValueError, TypeError, IndexError) as exc:
                totals['unmatched'] += 1
                print(f'Game {event_id}: {exc}')
    for name in ('thursday', 'saturday'):
        stat = totals[name]
        decided = stat['wins'] + stat['losses']
        stat['win_pct_excluding_pushes'] = round(100 * stat['wins'] / decided, 1) if decided else None
    output = {
        'season': YEAR,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'method': 'Matched immutable Thursday-evening and Saturday-morning public Yahoo snapshots graded against Thursday public line',
        'disclaimer': 'Only games with both picks before kickoff are graded. The Thursday public reference may not match the official private Yahoo group locked line; this comparison does not establish profitable predictions.',
        'totals': totals,
        'details': details,
    }
    (DATA / 'thursday_saturday_comparison.json').write_text(json.dumps(output, indent=2) + '\n')
    print('Thursday/Saturday audit', totals)

if __name__ == '__main__':
    run()
