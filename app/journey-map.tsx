'use client';
import {useEffect,useRef,useState} from 'react';
import type * as Leaflet from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './journey-map.css';
import {locateDevice,type LocationFix} from './location';
type Point=[number,number];
type Stop={code:string;name:string;lat:number;lon:number};
type Journey={label:string;minutes?:number;walk_m?:number;legs:{mode:string;service:string;from:string;to:string;points:Point[]}[]};
export type MapResult={source:string;notice:string;origin:{name:string;point:Point};destination:{name:string;point:Point};routes:Journey[]};
export default function JourneyMap({query,onRequest,onReply,locationFix,onOrigin,onSelect}:{onSelect?:(index:number)=>void;locationFix?:LocationFix;onOrigin?:(value:string)=>void;query?:{origin:string;destination:string;options?:Record<string,string>};onRequest:(a:string,b:string)=>void;onReply:(result:MapResult|null,error?:string)=>void}){
 const host=useRef<HTMLDivElement>(null),map=useRef<Leaflet.Map|null>(null),lib=useRef<typeof Leaflet|null>(null),lines=useRef<Leaflet.LayerGroup|null>(null);
 const [origin,setOrigin]=useState(''),[destination,setDestination]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<MapResult|null>(null),[selected,setSelected]=useState(0),[ready,setReady]=useState(false),[pick,setPick]=useState<'origin'|'destination'>('origin');
 const [locating,setLocating]=useState(false),[locationStatus,setLocationStatus]=useState('');
 const locationAbort=useRef<AbortController|null>(null),locationLayer=useRef<Leaflet.LayerGroup|null>(null);
 const pickRef=useRef(pick);useEffect(()=>{pickRef.current=pick;},[pick]);
 const requestId=useRef(0),abort=useRef<AbortController|null>(null);
 useEffect(()=>{
  let disposed=false;const controller=new AbortController();let instance:Leaflet.Map|undefined;
  void (async()=>{
   try{
    const L=await import('leaflet');if(disposed||!host.current)return;
    lib.current=L;instance=L.map(host.current).setView([1.36,103.82],11);map.current=instance;
    L.tileLayer('https://www.onemap.gov.sg/maps/tiles/Default/{z}/{x}/{y}.png',{minZoom:11,maxZoom:19,bounds:[[1.14,103.5],[1.5,104.51]],attribution:'<a href="https://www.onemap.gov.sg/" target="_blank" rel="noopener noreferrer">OneMap</a> © contributors | <a href="https://www.sla.gov.sg/" target="_blank" rel="noopener noreferrer">Singapore Land Authority</a>'}).on('tileerror',()=>{if(!disposed)setError('Some map tiles could not load. Journey search is still available.');}).addTo(instance);
    lines.current=L.layerGroup().addTo(instance);
    function choose(value:string){if(pickRef.current==='origin'){setOrigin(value);setPick('destination');}else setDestination(value);}
    instance.on('click',(e:Leaflet.LeafletMouseEvent)=>choose(`${e.latlng.lat.toFixed(6)},${e.latlng.lng.toFixed(6)}`));
    setReady(true);
    const response=await fetch('/api/map/stops',{signal:controller.signal});if(!response.ok)throw new Error();
    const data:{stops:Stop[]}=await response.json();if(disposed)return;
    const stops=L.layerGroup().addTo(instance),renderer=L.canvas();
    const draw=()=>{if(!instance)return;stops.clearLayers();if(instance.getZoom()<14)return;for(const stop of data.stops){if(!instance.getBounds().contains([stop.lat,stop.lon]))continue;const label=document.createElement('span');label.textContent=`${stop.code} · ${stop.name}`;L.circleMarker([stop.lat,stop.lon],{radius:5,color:'#206b53',weight:1,fillOpacity:.8,renderer,bubblingMouseEvents:false}).bindTooltip(label).on('click',()=>choose(stop.code)).addTo(stops);}};
    instance.on('moveend',draw);draw();
   }catch{if(!disposed)setError('Could not load the map or bus stops. Try refreshing.');}
  })();
  // These refs track network requests, not DOM nodes.
  // oxlint-disable-next-line react-hooks/exhaustive-deps
  return()=>{disposed=true;controller.abort();locationAbort.current?.abort();abort.current?.abort();requestId.current++;instance?.remove();map.current=null;};
 },[]);
 async function search(a=origin,b=destination,fromChat=false,options:Record<string,string>={}){
  if(!fromChat)onRequest(a,b);
  const id=++requestId.current;abort.current?.abort();const controller=new AbortController();abort.current=controller;
  setBusy(true);setError('');setResult(null);setSelected(0);
  const point=(s:string)=>/^\s*\d+\.\d+\s*,\s*\d+\.\d+\s*$/.test(s)?s.split(',').map(Number):s;
  try{const response=await fetch('/api/map/journey',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({origin:point(a),destination:point(b),options})});const data=await response.json() as MapResult & {error?:string};if(id!==requestId.current)return;if(!response.ok)throw new Error(data.error||'Journey search failed.');setResult(data);onReply(data);}
  catch(e){if(id===requestId.current){const message=e instanceof Error?e.message:'Journey search failed.';setError(message);onReply(null,message);}}
  finally{if(id===requestId.current)setBusy(false);}
 }
 // Query identity is the trigger; callback changes must not repeat a journey request.
 // oxlint-disable-next-line react-hooks/exhaustive-deps
 useEffect(()=>{let cancelled=false;void Promise.resolve().then(()=>{if(query&&!cancelled){setOrigin(query.origin);setDestination(query.destination);void search(query.origin,query.destination,true,query.options);}});return()=>{cancelled=true;};},[query]); // Search explicit chat route queries too.
 useEffect(()=>{
  const L=lib.current,m=map.current,layer=lines.current;if(!L||!m||!layer)return;layer.clearLayers();if(!result)return;
  const points:Point[]=[result.origin.point,result.destination.point];
  for(const [label,place] of [['Start',result.origin],['Destination',result.destination]] as const){const tip=document.createElement('span');tip.textContent=`${label}: ${place.name}`;L.circleMarker(place.point,{radius:9,color:label==='Start'?'#146747':'#c05e2d',fillOpacity:1}).bindTooltip(tip).addTo(layer);}
  for(const leg of result.routes[selected]?.legs||[]){if(leg.points.length<2)continue;points.push(...leg.points);L.polyline(leg.points,{color:leg.mode==='WALK'?'#68756e':'#167b59',weight:5,dashArray:leg.mode==='WALK'||result.source!=='OneMap'?'7 7':undefined}).addTo(layer);}
  m.fitBounds(L.latLngBounds(points),{padding:[25,25],maxZoom:16});
 },[result,selected,ready]);
 function applyLocation(fix:LocationFix){
  const value=`${fix.latitude.toFixed(6)},${fix.longitude.toFixed(6)}`;
  setOrigin(value);setPick('destination');onOrigin?.(value);
  const L=lib.current,m=map.current;
  if(L&&m){locationLayer.current?.remove();const layer=L.layerGroup().addTo(m);locationLayer.current=layer;const point:Point=[fix.latitude,fix.longitude];L.circle(point,{radius:fix.accuracy,color:'#2470cb',weight:1,fillOpacity:.12,interactive:false}).addTo(layer);L.circleMarker(point,{radius:8,color:'white',weight:3,fillColor:'#2470cb',fillOpacity:1}).bindTooltip('Your location').addTo(layer);m.setView(point,fix.accuracy>500?13:15);}
  setLocationStatus(`Starting point set to your location (accuracy about ${Math.round(fix.accuracy)} m). ${fix.accuracy>200?'This is approximate; check the blue accuracy circle. ':''}Choose a destination or ask in chat.`);
 }
 // An external location fix comes from the nearby-stops control.
 // oxlint-disable-next-line react-hooks/exhaustive-deps
 useEffect(()=>{let cancelled=false;void Promise.resolve().then(()=>{if(locationFix&&ready&&!cancelled)applyLocation(locationFix);});return()=>{cancelled=true;};},[locationFix,ready]);
 async function locate(){
  if(!navigator.geolocation){setLocationStatus('Location is unavailable in this browser. Pick your start on the map.');return;}
  locationAbort.current?.abort();const controller=new AbortController();locationAbort.current=controller;setLocating(true);setLocationStatus('Finding your location…');
  try{const fix=await locateDevice(navigator.geolocation,controller.signal,()=>setLocationStatus('Trying a more precise location fix…'));if(!controller.signal.aborted)applyLocation(fix);}
  catch(e){if(!controller.signal.aborted)setLocationStatus(e instanceof Error?e.message:'Location failed.');}
  finally{if(!controller.signal.aborted)setLocating(false);}
 }

 return <section className="journey-map" aria-label="Bus journey map"><div className="map-controls"><button type="button" aria-pressed={pick==='origin'} onClick={()=>setPick('origin')}>Pick start</button><button type="button" aria-pressed={pick==='destination'} onClick={()=>setPick('destination')}>Pick destination</button><button type="button" onClick={()=>{void locate();}} disabled={locating||busy}>{locating?'Locating…':'Use my location'}</button>{locating&&<button type="button" onClick={()=>{locationAbort.current?.abort();setLocating(false);setLocationStatus('Location cancelled. Pick your start on the map.');}}>Cancel location</button>}</div>{locationStatus&&<output aria-live="polite">{locationStatus}</output>}<div ref={host} className="map-canvas" aria-label="Interactive Singapore map"/><p className="map-hint">Tap the map to set your {pick==='origin'?'start':'destination'}.</p><form className="map-search" onSubmit={e=>{e.preventDefault();void search();}}><label>From<input value={origin} onChange={e=>setOrigin(e.target.value)} maxLength={100} placeholder="Woodlands Int" required/></label><label>To<input value={destination} onChange={e=>setDestination(e.target.value)} maxLength={100} placeholder="Hougang Int" required/></label><button disabled={busy}>{busy?'Finding buses…':'Find buses'}</button></form>{error&&<output>{error}</output>}{result&&<div className="map-results"><strong>{result.source}</strong>{result.routes.length===0&&<p>{result.notice}</p>}{result.routes.length>0&&result.source!=='OneMap'&&<p>January 2026 data · Dashed lines connect stops, not roads. Times are unverified.</p>}<div className="map-controls">{result.routes.map((r,i)=><button key={i} aria-pressed={selected===i} onClick={()=>{setSelected(i);onSelect?.(i);}}>{r.label}{r.minutes?` · ${r.minutes} min`:''}</button>)}</div><details><summary>Journey details</summary><p>{result.origin.name} → {result.destination.name}</p>{result.routes.length>0&&<p>{result.notice}</p>}<ol>{result.routes[selected]?.legs.map((l,i)=><li key={i}>{l.mode==='BUS'?`Bus ${l.service}`:'Walk'}: {l.from} → {l.to}</li>)}</ol></details></div>}</section>;
}
