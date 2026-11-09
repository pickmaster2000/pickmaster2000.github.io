"""Three-model experimental ATS vote; never overwrites live selections.

The three votes are statistical models trained on overlapping ESPN game data,
NOT independent LLMs. Save one immutable pre-kickoff record per ESPN event.
"""
import datetime as dt
import json
from build_predictions import DATA,YEAR,ALIASES,norm,fetch_results
from freeze_pregame import fixture_for

def canon(s):
    n=norm(s)
    return ALIASES.get(n,n)

def pair(g):return tuple(sorted((canon(g['favorite']),canon(g['underdog']))))
def count_models(game, models):
    votes=[]
    for label, predmap in models:
        p=predmap.get(pair(game))
        if not p:continue
        team=canon(p['recommended_team'])
        if team not in pair(game):continue
        votes.append({'model':label,'pick':p['recommended_team'],'canonical_pick':team,'edge_points':p.get('estimated_edge_points')})
    agree={}
    for v in votes:agree[v['canonical_pick']]=agree.get(v['canonical_pick'],0)+1
    winner=max(agree,key=agree.get) if agree else None
    n=agree.get(winner,0) if winner else 0
    return {'votes':votes,'agreement':f'{n} of {len(votes)}' if votes else 'No votes','majority_pick':next((g[k] for k in ('favorite','underdog') if canon(g[k])==winner),None) if n>=2 and len(votes)==3 else None,'full_three_model_vote':len(votes)==3,'unanimous':n==3 and len(votes)==3}

def run():
    now=dt.datetime.now(dt.timezone.utc)
    folder=DATA/'ensemble'
    folder.mkdir(exist_ok=True)
    snapshots=DATA/'ensemble_pregame'
    snapshots.mkdir(exist_ok=True)
    for path in sorted(DATA.glob('week[0-9][0-9].json')):
        week=int(path.stem[4:])
        try:
            slate=json.loads(path.read_text())
            names=['incumbent','offense_defense','recent_form']
            locations=[DATA/f'week{week:02}_predictions.json',DATA/'challenger'/path.name,DATA/'recent_form'/path.name]
            inputs=[json.loads(p.read_text()) for p in locations]
            events=fetch_results(week)
        except (OSError,ValueError,KeyError) as e:
            print('Ensemble week',week,'missing input',e)
            continue
        models=[(name,{pair(p):p for p in payload['predictions']}) for name,payload in zip(names,inputs)]
        records=[]
        for g in slate['games']:
            v=count_models(g,models)
            fixture=fixture_for(g,events)
            entry={'game':g,'espn_event_id':fixture[0] if fixture else None,'kickoff_utc':fixture[1].isoformat() if fixture else None,**v}
            records.append(entry)
            if fixture and fixture[1]>now and v['full_three_model_vote'] and v['majority_pick']:
                immutable=snapshots/f'{fixture[0]}.json'
                if not immutable.exists():
                    immutable.write_text(json.dumps({'season':YEAR,'week':week,'captured_at':now.isoformat(),**entry,'thursday_public_reference_verified':False,'warning':'First-observed live Yahoo public line, not verified official Yahoo contest line.'},indent=2)+'\n')
        (folder/path.name).write_text(json.dumps({'week':week,'season':YEAR,'generated_at':now.isoformat(),'experimental':True,'disclaimer':'Three correlated statistical predictors using ESPN public scores; NOT three independent AI services. Retrospective predictions change on reruns; evaluate only immutable prekickoff snapshots.','games':records},indent=2)+'\n')
        print('Ensemble week',week,'votes',sum(bool(x['majority_pick']) for x in records),'of',len(records))

if __name__=='__main__':run()
