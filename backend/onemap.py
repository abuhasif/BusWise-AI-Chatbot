"""Server-only OneMap adapter. Never expose credentials or upstream error bodies."""
import json, os, math, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime, timezone, timedelta

TOKEN_FILE=Path(__file__).resolve().parents[1]/'data/onemap-token.txt'
class Unavailable(Exception):pass

def token():
    return os.environ.get('ONEMAP_TOKEN','').strip() or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else '')

def request(path,params):
    key=token()
    if not key:raise Unavailable('OneMap routing is not connected. Using the January 2026 database.')
    req=urllib.request.Request('https://www.onemap.gov.sg/api/'+path+'?'+urllib.parse.urlencode(params),headers={'Authorization':key})
    try:
        with urllib.request.urlopen(req,timeout=15) as response:data=json.load(response)
        if not isinstance(data,dict) or data.get('error'):raise Unavailable('OneMap could not complete this request.')
        return data
    except urllib.error.HTTPError as error:
        if error.code in (401,403):raise Unavailable('OneMap token is invalid or expired. Update the local token file.') from None
        if error.code==404:raise Unavailable('OneMap found no bus journey between these points.') from None
        raise Unavailable('OneMap is unavailable or its request limit was reached.') from None
    except (OSError,ValueError):raise Unavailable('OneMap could not be reached. Try again shortly.') from None

def coordinates(value):
    if not isinstance(value,list) or len(value)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in value):raise ValueError('Choose a valid location.')
    if not 1.14<=value[0]<=1.5 or not 103.5<=value[1]<=104.51:raise ValueError('Choose a location in Singapore.')
    return value

def decode(encoded):
    points=[];index=0;lat=lon=0
    while index<len(encoded):
        values=[]
        for _ in range(2):
            result=shift=0
            while True:
                if index>=len(encoded) or shift>30:raise ValueError('Invalid route geometry')
                b=ord(encoded[index])-63;index+=1
                if not 0<=b<=63:raise ValueError('Invalid route geometry')
                result|=(b&31)<<shift;shift+=5
                if b<32:break
            values.append(~(result>>1) if result&1 else result>>1)
        lat+=values[0];lon+=values[1];points.append([lat/1e5,lon/1e5])
    return points

def itineraries(data):
    result=[]
    for item in data.get('plan',{}).get('itineraries',[]):
        legs=item.get('legs',[])
        # Fail closed: buses plus access/transfer walking only, never rail/ferry.
        if not legs or not any(l.get('mode')=='BUS' for l in legs) or any(l.get('mode') not in ('BUS','WALK') for l in legs):continue
        formatted=[]
        for leg in legs:
            encoded=leg.get('legGeometry',{}).get('points','')
            try:points=decode(encoded)
            except ValueError:points=[]
            formatted.append({'mode':leg['mode'],'service':str(leg.get('routeShortName') or leg.get('route') or ''),'from':str(leg.get('from',{}).get('name','')),'to':str(leg.get('to',{}).get('name','')),'points':points})
        result.append({'label':' → '.join(l['service'] or 'Bus' for l in formatted if l['mode']=='BUS'),'walk_m':round(sum(float(l.get('distance',0)) for l in legs if l.get('mode')=='WALK')),'minutes':round(item.get('duration',0)/60),'legs':formatted})
    return result

def route(start,end,options=None):
    options=options if isinstance(options,dict) else {}
    now=datetime.now(timezone(timedelta(hours=8)))
    if options.get('departure'):
        try:now=datetime.fromisoformat(options['departure']).replace(tzinfo=timezone(timedelta(hours=8)))
        except (ValueError,TypeError):raise ValueError('Invalid departure date/time')
    data=request('public/routingsvc/route',{'start':','.join(map(str,coordinates(start))),'end':','.join(map(str,coordinates(end))),'routeType':'pt','mode':'bus','date':now.strftime('%m-%d-%Y'),'time':now.strftime('%H:%M:%S'),'maxWalkDistance':500 if options.get('less_walking')=='true' else 1000,'numItineraries':3})
    routes=itineraries(data)
    if options.get('direct_only')=='true':routes=[r for r in routes if sum(l['mode']=='BUS' for l in r['legs'])==1]
    if options.get('less_walking')=='true':routes.sort(key=lambda r:r['walk_m'])
    return routes
