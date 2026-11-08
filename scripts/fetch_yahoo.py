import json, re, os, datetime, urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE='https://football.fantasysports.yahoo.com/college/pickdistribution?type=sc&week={}'
ROOT=Path(__file__).resolve().parents[1]
class TextParser(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.skip+=1
        if tag in ('td','th','tr','div','p','h3','h4','li','br'): self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
        if tag in ('td','th','tr','div','p','h3','h4','li'): self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip: self.parts.append(data)

def parse(html):
    p=TextParser(); p.feed(html)
    lines=[re.sub(r'\s+',' ',x).strip() for x in ''.join(p.parts).splitlines()]
    lines=[x for x in lines if x]
    games=[]
    # Public Yahoo page labels favorite, underdog, favorite pick percentage, and spread.
    # Parsing is deliberately conservative: no invented matches when structure changes.
    for i,line in enumerate(lines):
        if line!='Favorite': continue
        segment=lines[i:i+38]
        try:
            f=segment[1]
            fi=segment.index('Favorite Pick Percentage')
            fp=int(re.search(r'\d+',segment[fi+1]).group())
            ui=segment.index('Underdog')
            u=segment[ui+1]
            pi=segment.index('Underdog Pick Percentage')
            up=int(re.search(r'\d+',segment[pi+1]).group())
            # spread is expressed as e.g. '7.0 pts' near team record table
            tail=segment[pi+2:]
            sm=next((re.search(r'^(\d+(?:\.\d+)?)\s*pts$',t) for t in tail if re.search(r'^(\d+(?:\.\d+)?)\s*pts$',t)),None)
            if not sm or not f or not u or f==u: continue
            spread=float(sm.group(1))
            if not (0<=fp<=100 and 0<=up<=100 and abs(fp+up-100)<=2): continue
            key=(f,u)
            if key not in [(g['favorite'],g['underdog']) for g in games]:
                games.append({'favorite':f.lstrip('@ ').strip(),'underdog':u.lstrip('@ ').strip(),'favorite_home':f.startswith('@'),'underdog_home':u.startswith('@'),'favorite_spread':-spread,'favorite_pick_pct':fp,'underdog_pick_pct':up})
        except (ValueError,IndexError,AttributeError): continue
    return games

def main():
    week=int(os.getenv('WEEK','0') or 0)
    if not 1<=week<=14:
        # Refresh all weeks so next week's public listing appears automatically.
        weeks=range(1,15)
    else: weeks=[week]
    for w in weeks:
        url=BASE.format(w)
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; Pickmaster2000/1.0; personal project)','Accept':'text/html'})
            with urllib.request.urlopen(req,timeout=18) as r:
                html=r.read().decode('utf-8','replace')
            games=parse(html)
            if not games:
                print(f'Week {w}: no verified games parsed; keeping prior valid snapshot')
                continue
            data={'week':w,'source':'Yahoo public Pick Distribution (Spread and Confidence)','source_url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'games':games,'note':'Public pick percentages are not predictive cover probabilities. Public game selection may differ from your group.'}
            dest=ROOT/'data'/f'week{w:02}.json'
            dest.write_text(json.dumps(data,indent=2)+'\n')
            print(f'Week {w}: saved {len(games)} games')
        except Exception as e: print(f'Week {w}: request failed ({type(e).__name__}: {e}); keeping prior valid snapshot')
if __name__=='__main__': main()
