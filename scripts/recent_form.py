"""Third experimental ATS model: recent results, opponent-normalized by schedule.

Deliberately simpler than the full-season margin ridge and offense/defense models.
This is a statistical vote, NOT an independent AI service or verified injury model.
Uses only completed games from previous weeks.
"""
import datetime as dt
import json
from collections import defaultdict
from build_predictions import DATA, YEAR, extract, fetch_results, norm, ALIASES, names

def fit(history):
    teams=defaultdict(list)
    lookup={}
    amb=set()
    all_games=defaultdict(list)
    for stamp, _, home, away, neutral in history:
        hid,aid=str(home['team']['id']),str(away['team']['id'])
        hscore,ascore=float(home['score']),float(away['score'])
        home_margin=max(-40,min(40,hscore-ascore-(0 if neutral else 2.5)))
        all_games[hid].append((stamp,aid,home_margin))
        all_games[aid].append((stamp,hid,-home_margin))
        for t in (home,away):
            tid=str(t['team']['id'])
            for n in names(t['team']):
                n=ALIASES.get(n,n)
                if n in lookup and lookup[n]!=tid: amb.add(n)
                else:lookup[n]=tid
    for n in amb:lookup.pop(n,None)
    # First pass: regularized season scoring form; second pass incorporates opponents.
    base={tid:sum(m for _,_,m in rows)/(len(rows)+4.0) for tid,rows in all_games.items()}
    ratings={}
    for tid,rows in all_games.items():
        ordered=sorted(rows,key=lambda x:x[0],reverse=True)[:4]
        weights=[1.,.8,.65,.5][:len(ordered)]
        adjusted=[m+base.get(opponent,0) for (_,opponent,m) in ordered]
        ratings[tid]=sum(x*w for x,w in zip(adjusted,weights))/(sum(weights)+3.)
    return ratings,all_games,lookup

def predict(game,fit):
    ratings, histories, lookup=fit
    def get(name):
        n=norm(name)
        return lookup.get(ALIASES.get(n,n))
    a,b=get(game['favorite']),get(game['underdog'])
    if not a or not b or a==b or min(len(histories[a]),len(histories[b]))<3:
        return None
    adv=2.5 if game['favorite_home'] and not game['underdog_home'] else -2.5 if game['underdog_home'] and not game['favorite_home'] else 0
    margin=max(-40,min(40,ratings[a]-ratings[b]+adv))
    market=-float(game['favorite_spread'])
    # Market anchor pre-declared, no historical optimization.
    projection=.65*market+.35*margin
    edge=projection-market
    return {
        'favorite':game['favorite'],'underdog':game['underdog'],
        'recommended_team':game['favorite'] if edge>0 else game['underdog'],
        'projected_favorite_margin':round(projection,2),
        'estimated_edge_points':round(abs(edge),2),
        'model':'Third statistical challenger: last-four-game schedule-adjusted scoring',
        'signal':'watchlist' if abs(edge)>=1.5 else 'weak_lean'
    }

def run():
    slates=[]
    for path in sorted(DATA.glob('week[0-9][0-9].json')):
        slate=json.loads(path.read_text())
        if slate.get('games'):slates.append((int(slate['week']),slate))
    if not slates:return
    history_by_week={}
    for week in range(1,max(w for w,_ in slates)):
        try:history_by_week[week]=fetch_results(week)
        except Exception as e:print('Recent-form ESPN week',week,e)
    out=DATA/'recent_form'
    out.mkdir(exist_ok=True)
    for week,slate in slates:
        if week<4 or any(w not in history_by_week for w in range(1,week)):continue
        unique={}
        for prev in range(1,week):
            for item in extract(history_by_week[prev],dt.datetime(YEAR,12,31,tzinfo=dt.timezone.utc)):
                unique[item[1]]=item
        fitted=fit(sorted(unique.values()))
        picks=[p for g in slate['games'] if (p:=predict(g,fitted))]
        (out/f'week{week:02}.json').write_text(json.dumps({'season':YEAR,'week':week,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'experimental':True,'predictions':picks},indent=2)+'\n')
        print('Recent form week',week,len(picks))

if __name__=='__main__':run()
