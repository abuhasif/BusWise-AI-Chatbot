'use client';
import {useEffect,useRef,useState} from 'react';
import {LocateFixed,LoaderCircle,MapPin,X} from 'lucide-react';
import './nearby.css';
import type {LocationFix} from './location';
import './stop-search.css';
type Stop={code:string;name:string;road:string;distance_m?:number;services:string[]};
type Nearby={stops:Stop[];radius_m?:number;search?:boolean;total?:number};
export default function NearbyStops({disabled,onServices,onOrigin,onLocation}:{onLocation?:(fix:LocationFix)=>void;disabled:boolean;onServices:(code:string)=>void;onOrigin:(code:string)=>void}){
 const [loading,setLoading]=useState(false),[data,setData]=useState<Nearby|null>(null),[error,setError]=useState(''),[accuracy,setAccuracy]=useState<number|null>(null);
 const [searchOpen,setSearchOpen]=useState(false),[query,setQuery]=useState(''),[retrying,setRetrying]=useState(false);
 const generation=useRef(0);
 useEffect(()=>()=>{generation.current++;},[]);
 function dismiss(){generation.current++;setLoading(false);setData(null);setError('');setAccuracy(null);setSearchOpen(false);setRetrying(false);}
 function locate(){
  if(loading||disabled)return;
  if(!navigator.geolocation){setError('Location is unavailable in this browser. You can still enter a station name or stop code in chat.');return;}
  const attempt=++generation.current;setLoading(true);setData(null);setError('');setAccuracy(null);setRetrying(false);
  const requestFix=(precise:boolean)=>navigator.geolocation.getCurrentPosition(position=>{
   if(attempt!==generation.current)return;
   setAccuracy(Math.round(position.coords.accuracy));
   onLocation?.({latitude:position.coords.latitude,longitude:position.coords.longitude,accuracy:position.coords.accuracy});
   void fetch('/api/nearby',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({latitude:position.coords.latitude,longitude:position.coords.longitude})})
    .then(async response=>{if(!response.ok)throw new Error('lookup');return await response.json() as Nearby;})
    .then(result=>{if(attempt===generation.current)setData(result);})
    .catch(()=>{if(attempt===generation.current)setError('Could not look up nearby stops. Check that the local backend is running and try again.');})
    .finally(()=>{if(attempt===generation.current)setLoading(false);});
  },err=>{
   if(attempt!==generation.current)return;
   if(err.code!==1&&!precise){setRetrying(true);requestFix(true);return;}
   setLoading(false);setSearchOpen(true);setError(err.code===1?'Location permission was not granted. Allow location for this site in your browser settings, or enter a station name in chat.':err.code===3?'Your browser could not get a location fix. Try opening this app in Chrome or Edge with location allowed, or search for your station or road below.':'Your device could not determine its location. Try again or enter a station name in chat.');
  },{enableHighAccuracy:precise,timeout:precise?30000:12000,maximumAge:precise?30000:120000});
  requestFix(false);
 }
 async function search(){
  if(query.trim().length<2||loading||disabled)return;
  const attempt=++generation.current;setLoading(true);setError('');setData(null);setAccuracy(null);setRetrying(false);
  try{const response=await fetch('/api/stops/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:query.trim()}),signal:AbortSignal.timeout(15000)});if(!response.ok)throw new Error();const result=await response.json() as Nearby;if(attempt===generation.current)setData(result);}
  catch{if(attempt===generation.current)setError('Stop search is unavailable. Check that the local backend is running and try again.');}
  finally{if(attempt===generation.current)setLoading(false);}
 }
 return <section className="nearby" aria-label="Find nearby bus stops"><div className="nearby-toolbar"><button type="button" onClick={locate} disabled={disabled||loading} className="locate-button">{loading?<LoaderCircle size={15} className="spin"/>:<LocateFixed size={15}/>} {loading?(retrying?'Trying a more precise fix…':'Locating / searching…'):data?'Refresh my location':'Use my location'}</button><button type="button" className="locate-button" onClick={()=>setSearchOpen(v=>!v)}>Search by station or road</button>{(loading||data||error||searchOpen)&&<button type="button" className="nearby-close" onClick={dismiss} aria-label="Close nearby stops"><X size={16}/></button>}</div>{searchOpen&&<form className="stop-search" onSubmit={e=>{e.preventDefault();void search();}}><label className="sr-only" htmlFor="stop-search">Station, road or stop name</label><input id="stop-search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="e.g. Serangoon, Tampines Avenue 5" maxLength={100}/><button type="submit" disabled={loading||disabled||query.trim().length<2}>Search</button></form>}<div aria-live="polite">{error&&<p className="location-error">{error}</p>}{data&&<div className="nearby-panel"><div className="nearby-caption"><strong>{data.search?'Matching stops':'Nearby stops'}</strong><span>{data.search?`Showing ${data.stops.length} of ${data.total} matches · Not ordered by distance`:'Straight-line distance, not walking distance'}{accuracy!==null?` · Location accuracy ~${accuracy} m`:''}</span></div>{accuracy!==null&&accuracy>200&&<p className="location-error">Your location is approximate. Check the stop name and road before selecting.</p>}{data.stops.length===0?<p>{data.search?'No matching stops. Try a shorter station, stop or road name.':`No stops with recorded services within ${(data.radius_m||2000)/1000} km. Search by station or road instead.`}</p>:data.stops.map(stop=><article className="nearby-stop" key={stop.code}><div className="nearby-stop-title"><MapPin size={16}/><strong>{stop.name}</strong><span>{stop.distance_m===undefined?'':stop.distance_m<1000?`${stop.distance_m} m`:`${(stop.distance_m/1000).toFixed(1)} km`}</span></div><p>{stop.road} · Stop {stop.code}</p><div className="nearby-services">{stop.services.map(service=><span key={service}>{service}</span>)}</div><div className="nearby-actions"><button type="button" disabled={disabled} onClick={()=>onServices(stop.code)}>Show buses</button><button type="button" disabled={disabled} onClick={()=>{onOrigin(stop.code);dismiss();}}>Use as starting stop</button></div></article>)}<small>January 2026 services. Nearby stops can be on opposite sides of a road; check direction and safe pedestrian access.</small></div>}</div></section>;
}
