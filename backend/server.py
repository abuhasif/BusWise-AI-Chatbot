"""Local conversational intent extraction + deterministic SQLite answers."""
import json, math, re, sqlite3, urllib.request, urllib.error
import onemap
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
DB=Path(__file__).resolve().parents[1]/'data/bus.db'
MODEL='qwen3.5:9b'
def connect():
    c=sqlite3.connect(f'{DB.as_uri()}?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
def clean(value):return re.sub(r'[^a-z0-9 ]','',str(value).lower()).strip()
def normalize_stop(value):
    text=clean(value)
    for short,long in [('sgoon','serangoon'),('wdlands','woodlands'),('wlands','woodlands'),('stn','station'),('opp','opposite'),('aft','after'),('bef','before'),('rd','road'),('ave','avenue'),('ctrl','central'),('int','interchange')]:
        text=re.sub(r'\b'+short+r'\b',long,text)
    text=re.sub(r'\s+',' ',text).strip()
    # Explicit aliases avoid confusing an interchange with nearby station stops.
    return {'hougang interchange':'hougang central interchange'}.get(text,text)
def resolve(c,term,kind):
    term=re.sub(r'^(?:bus stop|stop)\s+','',str(term or '').strip(),flags=re.I)
    if not term:return []
    if re.fullmatch(r'\d{4,5}',term):return [r['code'] for r in c.execute('SELECT code FROM stops WHERE code=?',(term.zfill(5),))]
    key=clean(term); stations=c.execute('SELECT name,station_code,stop FROM stations WHERE kind=?',(kind,)).fetchall()
    matches=[r['stop'] for r in stations if key in (clean(r['name']),re.sub(r'^(dtl|nel|splrt) ','',clean(r['name']))) or key in [clean(x) for x in r['station_code'].split('/')]]
    if matches:return sorted(set(matches))
    exact=[r['code'] for r in c.execute('SELECT code,name,road FROM stops') if normalize_stop(r['name'])==normalize_stop(term)]
    if exact:return exact
    # Bare town names may name an interchange absent from the station mappings.
    # Match only a complete interchange name, never every stop in the town.
    return [r['code'] for r in c.execute('SELECT code,name FROM stops') if normalize_stop(r['name'])==normalize_stop(term)+' interchange']
def name(c,code):
    r=c.execute('SELECT name FROM stops WHERE code=?',(code,)).fetchone();return f"{code} · {r['name']}" if r else code
def distance_m(lat,lon,stop_lat,stop_lon):
    a,b=math.radians(lat),math.radians(stop_lat)
    h=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(math.radians(stop_lon-lon)/2)**2
    return 6371000*2*math.asin(math.sqrt(min(1,max(0,h))))
def nearby(latitude,longitude):
    if isinstance(latitude,bool) or isinstance(longitude,bool) or not isinstance(latitude,(float,int)) or not isinstance(longitude,(float,int)):
        raise ValueError('Coordinates must be numbers')
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90<=latitude<=90 or not -180<=longitude<=180:
        raise ValueError('Invalid coordinates')
    radius=2000
    with connect() as c:
        ranked=[]
        for row in c.execute('SELECT s.* FROM stops s WHERE s.lat IS NOT NULL AND s.lon IS NOT NULL AND EXISTS (SELECT 1 FROM routes r WHERE r.stop=s.code)'):
            dist=distance_m(latitude,longitude,row['lat'],row['lon'])
            if dist<=radius:ranked.append((dist,dict(row)))
        ranked.sort(key=lambda item:(item[0],item[1]['code']))
        result=[]
        for dist,row in ranked[:5]:
            services=[r[0] for r in c.execute('SELECT DISTINCT service FROM routes WHERE stop=?',(row['code'],))]
            services.sort(key=lambda s:(int(re.match(r'\d+',s)[0]) if re.match(r'\d+',s) else 9999,s))
            result.append({'code':row['code'],'name':row['name'],'road':row['road'],'distance_m':round(dist),'services':services})
    return {'stops':result,'radius_m':radius,'snapshot':'2026-01-05'}
def search_stops(query):
    if not isinstance(query,str) or not 2<=len(query.strip())<=100:raise ValueError('Enter 2–100 characters')
    normalize=normalize_stop
    q=normalize(query);tokens=q.split()
    with connect() as c:
        aliases={}
        for r in c.execute('SELECT name,station_code,stop FROM stations'):
            aliases.setdefault(r['stop'],[]).extend([r['name'],r['station_code']])
        matches=[]
        for r in c.execute('SELECT s.* FROM stops s WHERE EXISTS (SELECT 1 FROM routes r WHERE r.stop=s.code)'):
            label=normalize(r['name']);road=normalize(r['road']);hay=' '.join([r['code'],label,road,normalize(' '.join(aliases.get(r['code'],[])))])
            if all(token in hay for token in tokens):matches.append((0 if q in (r['code'],label) else 1 if q in label else 2,dict(r)))
        matches.sort(key=lambda item:(item[0],item[1]['name'],item[1]['code']))
        stops=[]
        for _,r in matches[:10]:
            services=[x[0] for x in c.execute('SELECT DISTINCT service FROM routes WHERE stop=? ORDER BY service',(r['code'],))]
            stops.append({'code':r['code'],'name':r['name'],'road':r['road'],'services':services})
    return {'stops':stops,'search':True,'total':len(matches),'snapshot':'2026-01-05'}
def direct(c,orig,dest):
    a,b=resolve(c,orig,'board'),resolve(c,dest,'alight')
    if not a or not b:return [],'I could not identify '+('the boarding location' if not a else 'the destination')+'. Use a five-digit bus stop code or a station name covered by the dataset.'
    if set(a)==set(b):return [],'You selected the same location. Tell me a different destination.'
    sql=f'''SELECT a.service,a.direction,a.stop AS board,b.stop AS alight,b.seq-a.seq AS stops FROM routes a JOIN routes b ON a.service=b.service AND a.direction=b.direction WHERE a.stop IN ({','.join('?' for _ in a)}) AND b.stop IN ({','.join('?' for _ in b)}) AND b.seq>a.seq AND a.ambiguous=0 AND b.ambiguous=0 ORDER BY stops,a.service LIMIT 12'''
    rows=c.execute(sql,a+b).fetchall();seen=set();cards=[]
    for r in rows:
        key=(r['service'],r['board'],r['alight'])
        if key in seen:continue
        seen.add(key);cards.append({'Service':r['service'],'Board':name(c,r['board']),'Alight':name(c,r['alight']),'Stops along route':r['stops']})
    answer=f"Found {len(cards)} direct option(s) in the January 2026 snapshot. Options are ordered by stop count, not travel time. Station matches use the supplied boarding/alighting mappings."
    if not cards:answer='No direct route was found in this filtered snapshot. This does not mean no journey exists; transfers and omitted services are not searched.'
    if cards:
        answer+=' Boarding and alighting stops are shown below; these are specific stops, not all locations within the named towns.'
    return cards,answer
def rule_intent(message,context):
    t=message.lower()
    if 'nearest' in t or 'near me' in t:return {'intent':'nearby'}
    options={k:context[k] for k in ('direct_only','less_walking','departure') if k in context}
    changed=False
    if re.search(r'direct (?:bus|buses)(?: only)?|no transfers',t):options['direct_only']='true';changed=True
    if re.search(r'allow transfers|transfers are okay',t):options['direct_only']='false';changed=True
    if re.search(r'less walking|least walking',t):options['less_walking']='true';changed=True
    when=re.search(r'\b(tomorrow|today)(?:\s+(?:morning\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?',t)
    if when:
        now=onemap.datetime.now(onemap.timezone(onemap.timedelta(hours=8)))
        date=now+onemap.timedelta(days=when[1]=='tomorrow')
        hour=int(when[2]) if when[2] else now.hour
        minute=int(when[3] or 0) if when[2] else now.minute
        if when[4]=='pm' and hour<12:hour+=12
        if when[4]=='am' and hour==12:hour=0
        if hour>23 or minute>59:return {'intent':'invalid_time'}
        options['departure']=date.replace(hour=hour,minute=minute,second=0,microsecond=0).isoformat();changed=True
        message=message[:when.start()]+message[when.end():]
    stripped=re.sub(r'direct (?:bus|buses)(?: only)?|no transfers|less walking(?: please)?|least walking|allow transfers|transfers are okay','',message,flags=re.I).strip()
    if changed and not stripped.strip(' .?!') and context.get('origin') and context.get('destination'):
        return {**context,**options,'intent':'route'}
    parsed=base_rule_intent(stripped,context)
    if parsed.get('intent')=='route':parsed.update(options)
    return parsed

def base_rule_intent(message,context):
    t=message.lower();p=dict(context);p['intent']='unknown'
    if re.search(r'live|arriv|free (bus|board)|disrupt|fare|fastest|nearest',t):return {'intent':'unsupported'}
    if 'opposite' in t or 'reverse' in t:
        return {'intent':'route','origin':context.get('destination',''),'destination':context.get('origin','')}
    m=re.search(r'from\s+(.+?)\s+to\s+(.+?)[?.!]*$',message,re.I)
    if m:return {'intent':'route','origin':m[1].strip(),'destination':m[2].rstrip('?.! ')}
    m=re.search(r'(?:what about|how about|to)\s+(.+?)[?.!]*$',message,re.I)
    if m and context.get('intent')=='route':return {**context,'destination':m[1].rstrip('?.! ')}
    stop=re.search(r'\b\d{5}\b',message);svc=re.search(r'(?:service|bus)\s+(\d{1,3}[A-Za-z]?)\b',message,re.I)
    if stop:p['stop']=stop[0]
    if svc:p['service']=svc[1].upper()
    if 'sunday' in t:p['day']='sun'
    elif 'saturday' in t:p['day']='sat'
    elif 'weekday' in t:p['day']='wd'
    timetable=bool(re.search(r'\b(last|first)\b',t)) or (context.get('intent')=='times' and not re.search(r'\b(list|which buses|buses at|services at|stops for)\b',t))
    if timetable:
        if not svc:
            bare=re.match(r'^\s*(\d{1,3}[A-Za-z]?)\b',message)
            if bare:p['service']=bare[1].upper()
        # Resolve short clarification replies without requiring a stop number.
        location=re.sub(r'\b(?:what|when|is|the|time|for|of|at|from|on|please|last|first|bus|service|what about|how about|sunday|saturday|weekday|weekdays)\b',' ',t)
        location=re.sub(r'\b\d{1,3}[a-z]?\b',' ',location)
        location=re.sub(r'\s+',' ',location).strip(' ?.!,')
        location=re.sub(r'^(?:about|how)\s*','',location).strip()
        if stop:p['stop']=stop[0]
        elif location:p['stop']=location
        p['intent']='times';return p
    if 'stops' in t and svc and not stop:p['intent']='service';return p
    if stop:p['intent']='stop';return p
    return p
def interpret(message,context,use_model=True):
    fallback=rule_intent(message,context)
    if fallback.get('intent')=='unsupported':return fallback,'rules'
    if use_model:
        schema={'type':'object','properties':{k:{'type':'string'} for k in ['intent','origin','destination','stop','service','day']},'required':['intent']}
        prompt='Extract a bus query as JSON. Never answer it or invent route facts. intent must be route, stop, times, service, or unknown. route uses origin and destination (station names or five digit stop codes); stop uses stop; times uses stop, service and day (wd/sat/sun); service lists stops for service. Preserve identifiers exactly. For follow-ups use context. Do not invent missing locations. Return only fields supported by the user/context.'
        body={'model':MODEL,'stream':False,'think':False,'format':schema,'options':{'temperature':0,'num_predict':512,'num_ctx':4096},'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'question':message,'context':context})}]}
        try:
            request=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=45) as response:d=json.loads(response.read())
            parsed=json.loads(d['message']['content']);parsed={k:v[:120] for k,v in parsed.items() if k in schema['properties'] and isinstance(v,str)}
            # Explicit deterministic inputs take precedence over model interpretation.
            if fallback['intent']!='unknown':parsed=fallback
            return parsed,'model'
        except (ValueError,KeyError,TimeoutError,OSError):pass
    return fallback,'rules'
def answer(message,context=None,use_model=True):
    if not isinstance(context,dict):context={}
    context={k:v[:120] for k,v in context.items() if k in ('intent','origin','destination','stop','service','day','direct_only','less_walking','departure') and isinstance(v,str)}
    p,mode=interpret(message,context,use_model);kind=p.get('intent');cards=[]
    with connect() as c:
        if kind=='route':cards,text=direct(c,p.get('origin'),p.get('destination'))
        elif kind=='stop':
            codes=resolve(c,p.get('stop'),'board')
            if not codes:text='Which bus stop? Give a five-digit stop code, such as 66009.'
            else:
                for code in codes:
                    services=[r[0] for r in c.execute('SELECT DISTINCT service FROM routes WHERE stop=? ORDER BY service',(code,))]
                    cards.append({'Stop':name(c,code),'Services':', '.join(services) or 'None in this snapshot'})
                text='These services are listed at your stop in the January 2026 snapshot.'
        elif kind=='times':
            codes=resolve(c,p.get('stop'),'board');svc=p.get('service','');day=p.get('day','wd');day=day if day in ('wd','sat','sun') else 'wd'
            if not svc:text='Tell me the service number. You can give a boarding stop name, such as Woodlands Int, and specify weekday, Saturday or Sunday.'
            elif not codes:
                text=(f"I could not match '{p['stop']}' to a stop in this snapshot. Which stop are you boarding service {svc} at? Use its name or select it with stop search." if p.get('stop') else f'Where are you boarding service {svc}? A stop name such as Woodlands Int is enough. You can also specify weekday, Saturday or Sunday.')
            else:
                for code in codes:
                    for r in c.execute(f'SELECT direction,seq,{day}_first AS first,{day}_last AS last FROM routes r WHERE stop=? AND service=? AND EXISTS (SELECT 1 FROM routes onward WHERE onward.service=r.service AND onward.direction=r.direction AND onward.seq>r.seq) ORDER BY direction,seq',(code,svc)):
                        fmt=lambda v:(str(v)[:2]+':'+str(v)[2:]) if v and re.fullmatch(r'\d{4}',str(v)) else 'Not recorded'
                        terminal=c.execute('SELECT s.name FROM routes r JOIN stops s ON s.code=r.stop WHERE r.service=? AND r.direction=? ORDER BY r.seq DESC LIMIT 1',(svc,r['direction'])).fetchone()
                        cards.append({'Service':svc,'Stop':name(c,code),'Towards':terminal['name'] if terminal else 'Not recorded','First bus':fmt(r['first']),'Last bus':fmt(r['last'])})
                text=(f"Recorded {'weekday' if day=='wd' else 'Saturday' if day=='sat' else 'Sunday'} boarding times, not live arrivals. Terminating-only route entries are excluded. Times beyond 24:00 refer to after midnight." if cards else 'No onward boarding service is recorded for that service at that stop in this snapshot.')
        elif kind=='service':
            svc=p.get('service','');rows=c.execute('SELECT r.direction,r.seq,r.stop,s.name FROM routes r JOIN stops s ON s.code=r.stop WHERE r.service=? ORDER BY r.direction,r.seq LIMIT 80',(svc,)).fetchall()
            cards=[{'Direction':r['direction'],'Sequence':r['seq'],'Stop':r['stop'],'Name':r['name']} for r in rows];text=f'Up to 80 recorded stops for service {svc}. Loop directions follow the source workbook.' if cards else 'Service not found in the filtered snapshot.'
        elif kind=='nearby':text='Use the Use my location button on the map to find your position, or Search by station or road below to choose a nearby stop.'
        elif kind=='invalid_time':text='Please enter a valid departure time, such as tomorrow at 8am.'
        elif kind=='unsupported':text='This snapshot cannot confirm live arrivals, current disruptions, fares, active free boarding, nearest walking routes or fastest journeys. I can look up direct routes, stop services and recorded first/last buses.'
        else:text='I can help with direct routes, bus stops and operating times. Try “from Serangoon to Bartley”, “buses at stop 66009”, or “last bus for service 100 at stop 66009 on Sunday”.'
    return {'answer':text,'cards':cards,'context':p,'mode':mode,'snapshot':'2026-01-05'}
def map_stops():
    with connect() as c:
        return {'stops':[dict(r) for r in c.execute('SELECT code,name,lat,lon FROM stops WHERE lat IS NOT NULL AND lon IS NOT NULL')]}

def transfer_routes(c,origin,destination):
    starts,ends=resolve(c,origin,'board'),resolve(c,destination,'alight')
    if not starts or not ends or set(starts)==set(ends):return []
    groups={}
    for r in c.execute('SELECT r.*,s.name,s.lat,s.lon FROM routes r JOIN stops s ON s.code=r.stop ORDER BY r.seq'):
        groups.setdefault((r['service'],r['direction']),[]).append(r)
    arrivals={}
    for key,rows in groups.items():
        for i,a in enumerate(rows):
            if a['stop'] not in starts or a['ambiguous']:continue
            for j in range(i+1,len(rows)):
                b=rows[j]
                if b['seq']<=a['seq'] or b['ambiguous']:continue
                arrivals.setdefault(b['stop'],[]).append((key,rows[i:j+1]))
    candidates=[]
    for key,rows in groups.items():
        for j,b in enumerate(rows):
            if b['stop'] not in ends or b['ambiguous']:continue
            for i in range(j):
                a=rows[i]
                if a['ambiguous'] or a['seq']>=b['seq']:continue
                for first,segment in arrivals.get(a['stop'],[]):
                    if first[0]==key[0]:continue
                    candidates.append((segment[-1]['seq']-segment[0]['seq']+b['seq']-a['seq'],first,key,segment,rows[i:j+1]))
    candidates.sort(key=lambda item:(item[0],item[1],item[2]))
    result=[];seen=set()
    for _,first,second,a,b in candidates:
        if (first,second) in seen:continue
        seen.add((first,second))
        def leg(key,rows):
            return {'mode':'BUS','service':key[0],'from':name(c,rows[0]['stop']),'to':name(c,rows[-1]['stop']),'points':[[r['lat'],r['lon']] for r in rows if r['lat'] is not None and r['lon'] is not None]}
        result.append({'label':f'Bus {first[0]} → {second[0]}','legs':[leg(first,a),leg(second,b)]})
        if len(result)==3:break
    return result

def map_journey(origin,destination,options=None):
    options=options if isinstance(options,dict) else {}
    with connect() as c:
        def locate(value,kind):
            if isinstance(value,list):
                point=onemap.coordinates(value)
                return {'name':f'{point[0]:.5f}, {point[1]:.5f}','point':point}
            if not isinstance(value,str) or not 1<=len(value.strip())<=100:raise ValueError('Enter a stop name or choose a point on the map.')
            codes=resolve(c,value,kind)
            if codes:
                row=c.execute('SELECT name,lat,lon FROM stops WHERE code=?',(codes[0],)).fetchone()
                return {'name':row['name'],'point':[row['lat'],row['lon']]}
            if onemap.token():
                data=onemap.request('common/elastic/search',{'searchVal':value,'returnGeom':'Y','getAddrDetails':'Y','pageNum':1})
                rows=data.get('results',[])
                if rows:
                    exact=[r for r in rows if clean(r.get('SEARCHVAL',''))==clean(value) or str(r.get('POSTAL',''))==value.strip()]
                    if len(exact)!=1:raise ValueError('Please specify the full place name or address. Possible matches: '+ '; '.join(str(r.get('SEARCHVAL','')) for r in rows[:3]))
                    row=exact[0]
                    return {'name':row.get('SEARCHVAL',value),'point':onemap.coordinates([float(row['LATITUDE']),float(row['LONGITUDE'])])}
            raise ValueError(f'Could not locate {value}. Try a full stop name or choose a map point.')
        a,b=locate(origin,'board'),locate(destination,'alight')
        if a['point']==b['point']:return {'origin':a,'destination':b,'routes':[],'source':'Location check','notice':'You selected the same starting point and destination. Choose a different destination.'}
        notice=''
        try:
            routes=onemap.route(a['point'],b['point'],options)
            return {'origin':a,'destination':b,'routes':routes,'source':'OneMap','notice':'Bus journeys for '+str(options.get('departure') or 'departure now')+'. '+('Direct buses only. ' if options.get('direct_only')=='true' else '')+('Ordered by walking distance among returned options. ' if options.get('less_walking')=='true' else '')+('No journey matching your preferences was returned.' if not routes else 'Select a journey to see its path.')}
        except onemap.Unavailable as error:notice=str(error)
        # The fallback never invents a walking route or a road-following line.
        def fallback_term(value,place):
            if isinstance(value,str):return value
            stops=nearby(*place['point'])['stops']
            if not stops:return ''
            stop=stops[0]
            place['name']+=f" — nearest recorded stop: {stop['name']} ({stop['distance_m']} m straight-line)"
            return stop['code']
        start_term,end_term=fallback_term(origin,a),fallback_term(destination,b)
        cards,message=direct(c,start_term,end_term)
        routes=[]
        for card in cards:
            start,end=card['Board'].split(' · ')[0],card['Alight'].split(' · ')[0]
            pair=c.execute('SELECT a.direction,a.seq AS first,b.seq AS last FROM routes a JOIN routes b ON a.service=b.service AND a.direction=b.direction WHERE a.service=? AND a.stop=? AND b.stop=? AND b.seq>a.seq AND a.ambiguous=0 AND b.ambiguous=0 ORDER BY b.seq-a.seq LIMIT 1',(card['Service'],start,end)).fetchone()
            if not pair:continue
            points=[[r['lat'],r['lon']] for r in c.execute('SELECT s.lat,s.lon FROM routes r JOIN stops s ON s.code=r.stop WHERE r.service=? AND r.direction=? AND r.seq BETWEEN ? AND ? ORDER BY r.seq',(card['Service'],pair['direction'],pair['first'],pair['last'])) if r['lat'] is not None and r['lon'] is not None]
            routes.append({'label':'Bus '+card['Service'],'legs':[{'mode':'BUS','service':card['Service'],'from':card['Board'],'to':card['Alight'],'points':points}]})
        if not routes and options.get('direct_only')!='true':routes=transfer_routes(c,start_term,end_term)
        return {'origin':a,'destination':b,'routes':routes,'source':'January 2026 database','notice':notice+(' Requested departure time and walking preference cannot be verified in the fallback. ' if options.get('departure') or options.get('less_walking')=='true' else '')+(' Checked direct buses only.' if options.get('direct_only')=='true' else ' Checked direct buses and one transfer at the same stop.')+' Ranked by stop count; connection times are not checked. Dashed lines join stops; they are not road or walking directions. '+('' if routes else 'No matching journey found. Routes with more transfers or omitted services may exist.')}

class Handler(BaseHTTPRequestHandler):
    def allowed(self):
        host=self.headers.get('Host','').split(':')[0]
        origin=self.headers.get('Origin')
        return host in ('localhost','127.0.0.1') and (origin is None or origin in ('http://localhost:3000','http://127.0.0.1:3000'))
    def reply(self,status,data):
        payload=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        if not self.allowed():return self.reply(403,{'error':'Local access only'})
        if self.path=='/api/map/stops':return self.reply(200,map_stops())
        if self.path!='/api/health':return self.reply(404,{'error':'Not found'})
        available=False
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=2) as r:available=any(m['name']==MODEL for m in json.loads(r.read())['models'])
        except (OSError,ValueError):pass
        self.reply(200,{'model_available':available,'model':MODEL,'database_available':DB.exists(),'snapshot':'2026-01-05'})
    def do_POST(self):
        if not self.allowed():return self.reply(403,{'error':'Local access only'})
        if self.path not in ('/api/chat','/api/nearby','/api/stops/search','/api/map/journey'):return self.reply(404,{'error':'Not found'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=8192:return self.reply(413,{'error':'Request too large'})
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict):return self.reply(400,{'error':'Expected a JSON object'})
            if self.path=='/api/map/journey':
                try:return self.reply(200,map_journey(data.get('origin'),data.get('destination'),data.get('options')))
                except (ValueError,onemap.Unavailable) as error:return self.reply(400,{'error':str(error)})
            if self.path=='/api/nearby':return self.reply(200,nearby(data.get('latitude'),data.get('longitude')))
            if self.path=='/api/stops/search':return self.reply(200,search_stops(data.get('query')))
            message=data.get('message')
            if not isinstance(message,str) or not 1<=len(message.strip())<=600:return self.reply(400,{'error':'Message must contain 1–600 characters'})
            self.reply(200,answer(message,data.get('context')))
        except (ValueError,TypeError):self.reply(400,{'error':'Invalid JSON request'})
        except Exception:self.reply(500,{'error':'Could not complete the database query'})
if __name__=='__main__':
    print('Buswise API listening at http://127.0.0.1:8765',flush=True);ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
