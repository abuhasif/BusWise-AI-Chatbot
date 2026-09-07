import json,urllib.request,time,sys
from pathlib import Path
sys.path.insert(0,'backend')
from server import connect
cases=[
('Direct route','How do I get from Woodlands Int to Hougang Int?',{},'route'),
('Transfer route','How do I get from Woodlands to Pasir Ris?',{},'route'),
('Natural wording','I am at Serangoon and want to reach Bartley. Which bus can I take?',{},'route'),
('Stop services','Which buses serve stop 66009?',{},'stop'),
('Last bus','Last bus 168 at Woodlands Int',{},'times'),
('Missing boarding stop','last bus 168',{},'times'),
('Stop clarification','168 woodlands int',{'intent':'times','service':'168'},'times'),
('Day follow-up','What about Sunday?',{'intent':'times','service':'168','stop':'Woodlands Int'},'times'),
('Destination follow-up','What about Hougang?',{'intent':'route','origin':'Woodlands Int','destination':'Pasir Ris'},'route'),
('Reverse journey','Opposite direction',{'intent':'route','origin':'Woodlands Int','destination':'Hougang Int'},'route'),
('First bus','First bus 161 at Woodlands Int on Saturday',{},'times'),
('Live arrivals','When will the next bus 168 arrive?',{},'unsupported'),
('Nearest stop','What is the nearest bus stop to me?',{},'unsupported'),
('Unknown place','From Woodlands to Atlantis',{},'route'),
('Unknown stop','Which buses serve stop 99999?',{},'stop'),
('Route time','How long does it take from Woodlands to Hougang?',{},'route'),
('Direct-only request','Direct bus only from Woodlands to Pasir Ris',{},'route'),
('Fare','How much is the bus fare from Woodlands to Hougang?',{},'unsupported')]
def post(path,data):
 req=urllib.request.Request('http://127.0.0.1:3000'+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
 except urllib.error.HTTPError as e:return json.load(e)
results=[]
for label,q,ctx,intent in cases:
 start=time.monotonic();reply=post('/api/chat',{'message':q,'context':ctx});p=reply.get('context',{});mapped=None;valid=True
 if p.get('intent')=='route' and p.get('origin') and p.get('destination'):
  mapped=post('/api/map/journey',{'origin':p['origin'],'destination':p['destination']})
  with connect() as c:
   for route in mapped.get('routes',[]):
    legs=route['legs']
    for leg in legs:
     a,b=leg['from'].split(' · ')[0],leg['to'].split(' · ')[0]
     valid=valid and bool(c.execute('SELECT 1 FROM routes a JOIN routes b ON a.service=b.service AND a.direction=b.direction WHERE a.service=? AND a.stop=? AND b.stop=? AND b.seq>a.seq AND a.ambiguous=0 AND b.ambiguous=0 LIMIT 1',(leg['service'],a,b)).fetchone())
    for a,b in zip(legs,legs[1:]):valid=valid and a['to']==b['from']
 item={'case':label,'question':q,'intent_match':p.get('intent')==intent,'route_facts_valid':valid,'seconds':round(time.monotonic()-start,1),'reply':reply,'map':mapped};results.append(item)
 print(json.dumps({'case':label,'intent':p.get('intent'),'valid':valid,'answer':(mapped or reply).get('error') or (mapped or reply).get('notice') or reply.get('answer'),'routes':[r['label'] for r in (mapped or {}).get('routes',[])],'cards':reply.get('cards') if intent=='times' else None}),flush=True)
Path('docs/evaluation/common-questions.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
