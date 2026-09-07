import json,time,urllib.request,urllib.error,sys
from pathlib import Path
sys.path.insert(0,'backend')
from server import connect
cases=[
('Woodlands interchange to Hougang interchange','From Woodlands Int to Hougang Int',None),
('Change destination','What about Pasir Ris?',1),
('Reverse journey','Opposite direction',2),
('Natural phrasing','I am at Serangoon and want to reach Bartley. Which bus can I take?',None),
('Stop-code route','From 46009 to 64009',None),
('Interchange abbreviation','From Wdlands Int to Hougang Ctrl Int',None),
('Stop services','Which buses serve stop 66009?',None),
('Service itinerary','List the stops for bus 161',None),
('Weekday last bus','Last bus 168 at Woodlands Int',None),
('Day change','What about Sunday?',9),
('First Saturday bus','First bus 161 at Woodlands Int on Saturday',None),
('Missing stop','last bus 168',None),
('Provide missing stop','Woodlands Int',12),
('Invalid stop code','Which buses serve stop 99999?',None),
('Nonexistent service','Last bus 999 at Woodlands Int',None),
('Unknown destination','From Woodlands to Atlantis',None),
('Identical endpoints','From Woodlands Int to Woodlands Int',None),
('Live arrivals','When will the next bus 168 arrive?',None),
('Fare question','How much is the fare from Woodlands to Hougang?',None),
('Nearest stop','Where is the nearest bus stop to me?',None),
('Direct-only constraint','Direct buses only from Woodlands to Pasir Ris',None),
('Reduce walking','Less walking please',1),
('Future departure','From Woodlands to Hougang tomorrow at 8am',None),
('Duration','How long does it take from Woodlands to Hougang?',None),
('Explain selected option','Where do I change for the second route?',2)]
def post(path,body):
 try:
  req=urllib.request.Request('http://127.0.0.1:3000'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=90) as response:return json.load(response)
 except urllib.error.HTTPError as e:return json.load(e)
 except Exception as e:return {'error':type(e).__name__}
results=[]
for i,(label,question,parent) in enumerate(cases,1):
 context=results[parent-1]['chat'].get('context',{}) if parent else {}
 started=time.monotonic();chat=post('/api/chat',{'message':question,'context':context});p=chat.get('context',{});journey=None
 if p.get('intent')=='route' and p.get('origin') and p.get('destination'):
  def point(v):
   try:
    parts=v.split(',');return [float(x) for x in parts] if len(parts)==2 else v
   except ValueError:return v
  journey=post('/api/map/journey',{'origin':point(p['origin']),'destination':point(p['destination'])})
 checks={}
 if journey and journey.get('routes'):
  checks['bus_walk_only']=all(l['mode'] in ('BUS','WALK') for r in journey['routes'] for l in r['legs'])
  checks['every_journey_has_bus']=all(any(l['mode']=='BUS' for l in r['legs']) for r in journey['routes'])
  checks['geometry_present']=all(len(l['points'])>=2 for r in journey['routes'] for l in r['legs'])
 with connect() as c:
  if p.get('intent')=='times' and chat.get('cards'):
   day=p.get('day','wd');day=day if day in ('wd','sat','sun') else 'wd';valid=[]
   for card in chat['cards']:
    rows=c.execute(f'SELECT {day}_first,{day}_last FROM routes r WHERE service=? AND stop=? AND EXISTS(SELECT 1 FROM routes n WHERE n.service=r.service AND n.direction=r.direction AND n.seq>r.seq)',(card['Service'],card['Stop'].split(' · ')[0])).fetchall()
    valid.append(any(str(row[0])==card['First bus'].replace(':','') and str(row[1])==card['Last bus'].replace(':','') for row in rows))
   checks['timetable_matches_snapshot']=all(valid)
  if i==7:checks['services_match_snapshot']=set(chat['cards'][0]['Services'].split(', '))=={r[0] for r in c.execute("SELECT DISTINCT service FROM routes WHERE stop='66009'")}
 item={'id':i,'scenario':label,'question':question,'follows':parent,'input_context':context,'seconds':round(time.monotonic()-started,2),'chat':chat,'journey':journey,'checks':checks};results.append(item)
 Path('docs/evaluation/qwen-25-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(json.dumps({'id':i,'scenario':label,'mode':chat.get('mode'),'context':p,'answer':chat.get('answer'),'source':(journey or {}).get('source'),'error':(journey or {}).get('error'),'routes':[{k:r[k] for k in ('label','minutes') if k in r} for r in (journey or {}).get('routes',[])],'checks':checks,'seconds':item['seconds']}),flush=True)
