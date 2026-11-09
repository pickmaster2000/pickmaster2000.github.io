"""Experimental, no-cost college football Elo ATS projections.

Uses public ESPN scoreboard results; not an injury, weather or AI model.
Fails closed: no pick when team identification or history is insufficient.
"""
import datetime as dt
import json
import math
import pathlib
import re
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
YEAR = 2026
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard'
ALIASES = {
    'florida st': 'florida state', 'pittsburgh': 'pittsburgh',
    'miami fl': 'miami', 'iowa st': 'iowa state', 'ohio st': 'ohio state',
    'mississippi st': 'mississippi state', 'kansas st': 'kansas state',
    'arizona st': 'arizona state', 'oregon st': 'oregon state',
    'boise st': 'boise state', 'oklahoma st': 'oklahoma state',
    'n carolina': 'north carolina', 'mississippi': 'ole miss',
    'smu': 'smu', 'ucf': 'ucf', 'tcu': 'tcu', 'usc': 'usc',
    'n carolina': 'north carolina', 'north carolina': 'north carolina',
    'ole miss': 'ole miss', 'miami fl': 'miami',
    'texas a m': 'texas a&m', 'wake forest': 'wake forest',
    'app state': 'appalachian state', 'fla atlantic': 'florida atlantic',
}

def norm(s):
    s = s.casefold().replace('&', ' and ')
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

ALIASES = {norm(k): norm(v) for k, v in ALIASES.items()}

def names(team):
    result = set()
    for key in ('displayName', 'shortDisplayName', 'name', 'abbreviation'):
        value = team.get(key)
        if value:
            result.add(norm(value))
    return result

def fetch_results(week):
    params = urllib.parse.urlencode({'dates': YEAR, 'week': week, 'groups': 80, 'limit': 300})
    req = urllib.request.Request(ESPN + '?' + params, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.load(response)
    if not isinstance(data.get('events'), list):
        raise ValueError('ESPN scoreboard response has no events list')
    return data['events']

def extract(events, before):
    out = []
    for event in events:
        try:
            competition = event['competitions'][0]
            status = competition.get('status') or event.get('status') or {}
            if not status.get('type', {}).get('completed'):
                continue
            start = dt.datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
            if start >= before:
                continue
            competitors = competition['competitors']
            if len(competitors) != 2:
                continue
            home = next(c for c in competitors if c.get('homeAway') == 'home')
            away = next(c for c in competitors if c.get('homeAway') == 'away')
            if not home.get('score') or not away.get('score'):
                continue
            out.append((start, str(event['id']), home, away, bool(competition.get('neutralSite'))))
        except (KeyError, IndexError, ValueError, StopIteration, TypeError):
            continue
    return out

def run():
    snapshots = []
    for path in sorted(DATA.glob('week[0-9][0-9].json')):
        try:
            data = json.loads(path.read_text())
            if data.get('games'):
                snapshots.append((int(data['week']), data))
        except (ValueError, KeyError):
            continue
    if not snapshots:
        print('No Yahoo game snapshots; skipping predictions')
        return
    # Cache scoreboard weeks. Never use future games to forecast a past week.
    results_by_week = {}
    for week in range(1, max(w for w, _ in snapshots)):
        try:
            events = fetch_results(week)
            results_by_week[week] = events
            print(f'ESPN week {week}: {len(events)} scoreboard events')
        except Exception as exc:
            print(f'ESPN week {week}: unavailable ({type(exc).__name__}: {exc})')
    for week, snapshot in snapshots:
        # Week 1 cannot have in-season ratings; later weeks need complete prior-week fetches.
        if week < 4 or any(w not in results_by_week for w in range(1, week)):
            print(f'Week {week}: insufficient complete historical scoreboard data; no predictions written')
            continue
        kickoff_cutoff = dt.datetime(YEAR, 12, 31, tzinfo=dt.timezone.utc)
        games = {}
        for prev in range(1, week):
            for item in extract(results_by_week[prev], kickoff_cutoff):
                games[item[1]] = item
        ordered = sorted(games.values(), key=lambda x: (x[0], x[1]))
        # Fit a regularized margin-of-victory team rating, in POINTS.
        # Previous Elo ratings were calibrated to win odds, then divided by an
        # arbitrary 28 Elo-points-per-point; that understated favorite margins.
        counts = {}
        team_names = {}
        fixtures = []
        for _, _, home, away, neutral in ordered:
            hid, aid = home['team']['id'], away['team']['id']
            for c in (home, away):
                tid = c['team']['id']
                team_names.setdefault(tid, set()).update(names(c['team']))
                counts[tid] = counts.get(tid, 0) + 1
            home_field = 0.0 if neutral else 2.5
            actual_margin = float(home['score']) - float(away['score']) - home_field
            # Limit outlier blowouts before fitting opponent-adjusted ratings.
            fixtures.append((hid, aid, max(-42.0, min(42.0, actual_margin))))
        ratings = {tid: 0.0 for tid in counts}
        # Regularized least squares / Jacobi iterations. The 6-game prior
        # prevents wildly exaggerated estimates with sparse schedules.
        for _ in range(60):
            totals = {tid: 0.0 for tid in counts}
            for hid, aid, margin in fixtures:
                totals[hid] += margin + ratings[aid]
                totals[aid] += ratings[hid] - margin
            updated = {tid: totals[tid] / (counts[tid] + 6.0) for tid in counts}
            average = sum(updated.values()) / max(1, len(updated))
            ratings = {tid: updated[tid] - average for tid in updated}
        lookup = {}
        ambiguous = set()
        for tid, variations in team_names.items():
            for variation in variations:
                if variation in lookup and lookup[variation] != tid:
                    ambiguous.add(variation)
                else:
                    lookup[variation] = tid
        for item in ambiguous:
            lookup.pop(item, None)
        def resolve(name):
            n = norm(name)
            n = ALIASES.get(n, n)
            return lookup.get(n)
        predictions = []
        for game in snapshot['games']:
            fav, dog = resolve(game['favorite']), resolve(game['underdog'])
            if not fav or not dog or fav == dog or counts.get(fav, 0) < 3 or counts.get(dog, 0) < 3:
                print(f"Week {week}: unmatched/insufficient history: {game['favorite']} / {game['underdog']}")
                continue
            if game.get('favorite_home') == game.get('underdog_home'):
                home_adjust = 0
            else:
                home_adjust = 2.5 if game.get('favorite_home') else -2.5
            # Elo points-to-margin conversion is heuristic, not backtested.
            raw_margin = max(-45.0, min(45.0, ratings[fav] - ratings[dog] + home_adjust))
            market_margin = -float(game['favorite_spread'])
            # Shrink toward the market as a more credible baseline than a
            # small, noisy single-season model. This is NOT an ATS win probability.
            projected = 0.70 * market_margin + 0.30 * raw_margin
            edge = projected - market_margin
            if abs(edge) < 1.5:
                continue
            # No false 'confidence' probabilities: uncalibrated point edge only.
            predictions.append({
                'favorite': game['favorite'], 'underdog': game['underdog'],
                'projected_favorite_margin': round(projected, 2),
                'recommended_team': game['favorite'] if edge > 0 else game['underdog'],
                'estimated_edge_points': round(abs(edge), 2),
                'model': 'Regularized opponent-adjusted scores, 70% market anchor',
                'data_quality': 'Experimental, not backtested; injuries/weather not included',
            })
        if not predictions:
            print(f'Week {week}: no sufficiently verified predictions; leaving prior file unchanged')
            continue
        payload = {'week': week, 'season': YEAR, 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'source': 'ESPN public completed-game scoreboard + Yahoo spread', 'model': 'Regularized scoring with market anchoring',
                   'warning': 'Uncalibrated model; no injuries, weather, or multi-AI analysis. Do not interpret displayed ATS percentages as validated probabilities.',
                   'predictions': predictions}
        path = DATA / f'week{week:02}_predictions.json'
        path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
        print(f'Week {week}: saved {len(predictions)} preliminary ATS predictions')

if __name__ == '__main__':
    run()
