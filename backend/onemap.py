"""Server-only OneMap adapter. Never expose credentials or upstream error bodies."""
import base64, json, os, math, threading, time, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime, timezone, timedelta

TOKEN_FILE=Path(__file__).resolve().parents[1]/'data/onemap-token.txt'
class Unavailable(Exception):pass

AUTH_URL='https://www.onemap.gov.sg/api/auth/post/getToken'
# OneMap tokens last 3 days. Renew this long before expiry so requests never race it.
RENEW_BEFORE=6*3600
_cache={'token':'','expires':0.0};_lock=threading.Lock()

def credentials():
    return os.environ.get('ONEMAP_EMAIL','').strip(),os.environ.get('ONEMAP_PASSWORD','')

def expiry(jwt):
    """Unix expiry from a token's payload (not verified; only used to decide when to renew)."""
    try:
        part=jwt.split('.')[1];payload=json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))
        return float(payload['exp'])
    except (IndexError,KeyError,TypeError,ValueError):return 0.0

def sign_in():
    """Exchange ONEMAP_EMAIL/ONEMAP_PASSWORD for a fresh token. Never logs or returns the password."""
    email,password=credentials()
    req=urllib.request.Request(AUTH_URL,data=json.dumps({'email':email,'password':password}).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=15) as response:data=json.load(response)
    except urllib.error.HTTPError:raise Unavailable('OneMap sign-in failed. Check ONEMAP_EMAIL and ONEMAP_PASSWORD.') from None
    except (OSError,ValueError):raise Unavailable('OneMap could not be reached. Try again shortly.') from None
    key=data.get('access_token') if isinstance(data,dict) else None
    if not isinstance(key,str) or not key:raise Unavailable('OneMap sign-in failed. Check ONEMAP_EMAIL and ONEMAP_PASSWORD.')
    try:expires=float(data.get('expiry_timestamp') or 0)
    except (TypeError,ValueError):expires=0.0
    return key,expires or expiry(key) or time.time()+3*86400

def token(refresh=False):
    """Credentials renew automatically; otherwise use ONEMAP_TOKEN or data/onemap-token.txt."""
    email,password=credentials()
    if email and password:
        with _lock:
            if refresh or not _cache['token'] or time.time()>_cache['expires']-RENEW_BEFORE:
                _cache['token'],_cache['expires']=sign_in()
            return _cache['token']
    key=os.environ.get('ONEMAP_TOKEN','').strip() or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else '')
    expires=expiry(key) if key else 0.0
    if expires and expires<time.time():
        when=datetime.fromtimestamp(expires,timezone(timedelta(hours=8)))
        raise Unavailable(f'The OneMap token expired on {when.day} {when:%B %Y}. Set ONEMAP_EMAIL and ONEMAP_PASSWORD so it renews automatically.')
    return key

def request(path,params,retry=True):
    key=token()
    if not key:raise Unavailable('OneMap routing is not connected. Using the January 2026 database.')
    req=urllib.request.Request('https://www.onemap.gov.sg/api/'+path+'?'+urllib.parse.urlencode(params),headers={'Authorization':key})
    try:
        with urllib.request.urlopen(req,timeout=15) as response:data=json.load(response)
        if not isinstance(data,dict) or data.get('error'):raise Unavailable('OneMap could not complete this request.')
        return data
    except urllib.error.HTTPError as error:
        if error.code in (401,403):
            # A rejected token is renewed once when credentials are configured.
            if retry and all(credentials()):
                token(refresh=True);return request(path,params,retry=False)
            raise Unavailable('OneMap token is invalid or expired. Set ONEMAP_EMAIL and ONEMAP_PASSWORD so it renews automatically.') from None
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
