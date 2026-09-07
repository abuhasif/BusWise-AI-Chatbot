"""Read the provided workbook; create a separate queryable snapshot. Never execute its notebook."""
import argparse, collections, hashlib, json, sqlite3
from pathlib import Path
import openpyxl
ROOT=Path(__file__).resolve().parents[1]
def ingest(source):
    wb=openpyxl.load_workbook(source,read_only=True,data_only=True)
    def records(name):
        it=wb[name].iter_rows(values_only=True); headers=next(it)
        return [dict(zip(headers,r)) for r in it if any(v is not None for v in r)]
    stops, routes=records('BusStops'),records('BusRoutes')
    code=lambda v:str(int(v)).zfill(5)
    db=ROOT/'data/bus.db';db.parent.mkdir(exist_ok=True)
    c=sqlite3.connect(db)
    c.executescript('DROP TABLE IF EXISTS stops; DROP TABLE IF EXISTS routes; DROP TABLE IF EXISTS stations; DROP TABLE IF EXISTS metadata; CREATE TABLE stops(code TEXT PRIMARY KEY,name TEXT,road TEXT,lat REAL,lon REAL); CREATE TABLE routes(service TEXT,direction INTEGER,seq INTEGER,stop TEXT,distance REAL,wd_first TEXT,wd_last TEXT,sat_first TEXT,sat_last TEXT,sun_first TEXT,sun_last TEXT,ambiguous INTEGER); CREATE TABLE stations(name TEXT,station_code TEXT,stop TEXT,kind TEXT); CREATE TABLE metadata(json TEXT);')
    c.executemany('INSERT INTO stops VALUES(?,?,?,?,?)',[(code(s['BusStopCode']),s['Description'],s['RoadName'],s['Latitude'],s['Longitude']) for s in stops])
    keys=collections.Counter((str(r['ServiceNo']),r['Direction'],r['StopSequence']) for r in routes)
    bad={(s,d) for (s,d,q),count in keys.items() if count>1}
    c.executemany('INSERT INTO routes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',[(str(r['ServiceNo']),r['Direction'],r['StopSequence'],code(r['BusStopCode']),r['Distance'],*[r[x] for x in ['WD_FirstBus','WD_LastBus','SAT_FirstBus','SAT_LastBus','SUN_FirstBus','SUN_LastBus']],int((str(r['ServiceNo']),r['Direction']) in bad)) for r in routes])
    for sheet,kind in [('FreeBoarding','board'),('FreeAlighting','alight')]:
        c.executemany('INSERT INTO stations VALUES(?,?,?,?)',[(r['Station Name'],r['Station Code'],code(r['Bus Stop Code']),kind) for r in records(sheet)])
    meta={'snapshot':'2026-01-05','source':Path(source).name,'sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),'stops':len(stops),'services':len({r['ServiceNo'] for r in routes}),'route_records':len(routes),'ambiguous_directions':[list(x) for x in sorted(bad)],'limitations':['Selected services; most A/B/C/T variants filtered out','Loop directions modified in source workbook','No live arrivals, disruptions, fares or free-boarding activation','Ambiguous route directions excluded from direct routing']}
    c.execute('INSERT INTO metadata VALUES(?)',(json.dumps(meta),));c.executescript('CREATE INDEX route_stop ON routes(stop); CREATE INDEX route_order ON routes(service,direction,seq);');c.commit();c.close();wb.close()
    print(json.dumps(meta,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workbook');ingest(p.parse_args().workbook)
