"""Forward-only ensemble evaluation on immutable pregame three-model votes."""
import datetime as dt
import json
from build_predictions import DATA,YEAR,fetch_results,ALIASES,names,norm

def canon(s):
    n=norm(s)
    return ALIASES.get(n,n)

def outcome(event,game):
    comp=event['competitions'][0]
    status=comp.get('status') or event.get('status') or {}
    if not status.get('type',{}).get('completed'):return None
    out={}
    for entry in comp['competitors']:
        forms=names(entry['team'])
        forms|={ALIASES.get(x,x) for x in forms}
        for name in (canon(game['favorite']),canon(game['underdog'])):
            if name in forms:out[name]=float(entry['score'])
    if len(out)!=2:return 'unmatched'
    cover=out[canon(game['favorite'])]-out[canon(game['underdog'])]+float(game['favorite_spread'])
    return cover

def grade(pick,game,cover):
    if abs(cover)<.01:return 'pushes'
    return 'wins' if ((cover>0)==(canon(pick)==canon(game['favorite']))) else 'losses'

def run():
    aggregate={key:{'wins':0,'losses':0,'pushes':0} for key in ('majority','incumbent','offense_defense','recent_form','always_underdog','unanimous')}
    total={'recorded':0,'pending':0,'unmatched':0,'decided':0}
    completed=[]
    event_cache={}
    for path in sorted((DATA/'ensemble_pregame').glob('*.json')):
        try:
            item=json.loads(path.read_text())
            kickoff=dt.datetime.fromisoformat(item['kickoff_utc'])
            captured=dt.datetime.fromisoformat(item['captured_at'])
            if captured>=kickoff:
                total['unmatched']+=1
                continue
            total['recorded']+=1
            week=int(item['week'])
            if week not in event_cache:
                event_cache[week]={str(x['id']):x for x in fetch_results(week)}
            event=event_cache[week].get(item['espn_event_id'])
            if not event:
                total['unmatched']+=1
                continue
            cover=outcome(event,item['game'])
            if cover is None:
                total['pending']+=1
                continue
            if cover=='unmatched':
                total['unmatched']+=1
                continue
            vote_by_model={x['model']:x['pick'] for x in item['votes']}
            votes={'majority':item['majority_pick'],'always_underdog':item['game']['underdog'],**vote_by_model}
            if item.get('unanimous'):votes['unanimous']=item['majority_pick']
            for name,pick in votes.items():
                if pick:aggregate[name][grade(pick,item['game'],cover)]+=1
            total['decided']+=1
            completed.append({'week':week,'event_id':item['espn_event_id'],'agreement':item['agreement'],'majority_result':grade(item['majority_pick'],item['game'],cover)})
        except (OSError,KeyError,TypeError,ValueError,IndexError) as e:
            total['unmatched']+=1
            print('Ensemble result excluded',path.name,e)
    for entry in aggregate.values():
        n=entry['wins']+entry['losses']
        entry['win_pct_excluding_pushes']=round(100*entry['wins']/n,1) if n else None
    output={'season':YEAR,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'method':'First-observed pregame three-model majority on Yahoo public spread; same matched games for main and underdog baseline',
            'warning':'Correlated models; no proven benefit. Results are only first captured prekickoff snapshots; public spreads may differ from Yahoo official contest lines.',
            'total':total,'models':aggregate,'completed':completed}
    (DATA/'ensemble_results.json').write_text(json.dumps(output,indent=2)+'\n')
    print('Ensemble forward results',total,aggregate['majority'])

if __name__=='__main__':run()
