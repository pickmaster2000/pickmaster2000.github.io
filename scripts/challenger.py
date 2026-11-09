"""Experimental challenger model: opponent-adjusted offense and defense.

Uses ONLY completed ESPN games from weeks preceding each Yahoo contest week.
The existing production picks stay unchanged. No injuries/weather are claimed.
"""
import datetime as dt
import json
from collections import defaultdict

from build_predictions import ALIASES, DATA, YEAR, extract, fetch_results, names, norm

BASE_POINTS = 27.0
HOME_POINTS = 1.25
PRIOR_GAMES = 5.0

def fit_scoring(ordered):
    """Ridge-regularized opponent adjusted scoring, two separate team components."""
    records = []
    counts = defaultdict(int)
    variations = defaultdict(set)
    for _, _, home, away, neutral in ordered:
        hid, aid = str(home['team']['id']), str(away['team']['id'])
        variations[hid].update(names(home['team']))
        variations[aid].update(names(away['team']))
        counts[hid] += 1
        counts[aid] += 1
        hs = min(65.0, max(0.0, float(home['score'])))
        ass = min(65.0, max(0.0, float(away['score'])))
        adj = 0 if neutral else HOME_POINTS
        records.append((hid, aid, hs, ass, adj))
    offense = {k: 0.0 for k in counts}
    defense = {k: 0.0 for k in counts}
    # Offense: points scored ABOVE league average. Defense: points allowed ABOVE league average.
    for _ in range(40):
        off_sum = defaultdict(float)
        def_sum = defaultdict(float)
        for hid, aid, hs, ass, adj in records:
            off_sum[hid] += hs - BASE_POINTS - adj - defense[aid]
            off_sum[aid] += ass - BASE_POINTS + adj - defense[hid]
            def_sum[aid] += hs - BASE_POINTS - adj - offense[hid]
            def_sum[hid] += ass - BASE_POINTS + adj - offense[aid]
        next_off = {tid: off_sum[tid] / (counts[tid] + PRIOR_GAMES) for tid in counts}
        next_def = {tid: def_sum[tid] / (counts[tid] + PRIOR_GAMES) for tid in counts}
        offense, defense = next_off, next_def
    lookup, collision = {}, set()
    for tid, nameset in variations.items():
        for n in nameset:
            expanded = {n, ALIASES.get(n, n)}
            for alias in expanded:
                if alias in lookup and lookup[alias] != tid:
                    collision.add(alias)
                else:
                    lookup[alias] = tid
    for key in collision:
        lookup.pop(key, None)
    return offense, defense, counts, lookup

def predict(game, fit):
    offense, defense, counts, lookup = fit
    def resolve(name):
        n = norm(name)
        return lookup.get(ALIASES.get(n, n)) or lookup.get(n)
    fav, dog = resolve(game['favorite']), resolve(game['underdog'])
    if not fav or not dog or fav == dog or min(counts[fav], counts[dog]) < 3:
        return None
    fav_home, dog_home = bool(game['favorite_home']), bool(game['underdog_home'])
    home_adv = HOME_POINTS * 2 if fav_home and not dog_home else -HOME_POINTS * 2 if dog_home and not fav_home else 0.0
    fav_score = BASE_POINTS + offense[fav] + defense[dog]
    dog_score = BASE_POINTS + offense[dog] + defense[fav]
    raw_margin = max(-45.0, min(45.0, fav_score - dog_score + home_adv))
    market_margin = -float(game['favorite_spread'])
    # Fixed in advance of this audit, NOT optimized to historical ATS results.
    projected = 0.7 * market_margin + 0.3 * raw_margin
    edge = projected - market_margin
    return {
        'favorite': game['favorite'], 'underdog': game['underdog'],
        'projected_favorite_margin': round(projected, 2),
        'recommended_team': game['favorite'] if edge > 0 else game['underdog'],
        'estimated_edge_points': round(abs(edge), 2),
        'signal': 'watchlist' if abs(edge) >= 1.5 else 'weak_lean',
        'model': 'Challenger: opponent-adjusted offense and defense, anchored to market',
        'data_quality': 'Experimental challenger, no validated advantage. No injuries/weather.',
    }

def run():
    snapshots = []
    for path in sorted(DATA.glob('week[0-9][0-9].json')):
        payload = json.loads(path.read_text())
        if payload.get('games'):
            snapshots.append((int(payload['week']), payload))
    if not snapshots:
        return
    scored = {}
    for week in range(1, max(week for week, _ in snapshots)):
        try:
            scored[week] = fetch_results(week)
        except Exception as exc:
            print(f'Challenger: ESPN week {week} error {exc}')
    outdir = DATA / 'challenger'
    outdir.mkdir(exist_ok=True)
    for week, slate in snapshots:
        if week < 4 or any(w not in scored for w in range(1, week)):
            continue
        historical = {}
        cutoff = dt.datetime(YEAR, 12, 31, tzinfo=dt.timezone.utc)
        for w in range(1, week):
            for game in extract(scored[w], cutoff):
                historical[game[1]] = game
        fit = fit_scoring(sorted(historical.values(), key=lambda x: (x[0], x[1])))
        predictions = [p for g in slate['games'] if (p := predict(g, fit))]
        payload = {
            'season': YEAR, 'week': week,
            'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'status': 'CHALLENGER ONLY. Not production picks. Retrospective evaluation has line-timing limitations.',
            'predictions': predictions,
        }
        (outdir / f'week{week:02}.json').write_text(json.dumps(payload, indent=2) + '\n')
        print(f'Challenger week {week}: generated {len(predictions)} exploratory picks')

if __name__ == '__main__':
    run()
