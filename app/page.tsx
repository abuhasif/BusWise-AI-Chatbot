'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import JourneyMap,{type MapResult} from './journey-map';
import {explainJourney} from './route-conversation';
import type {LocationFix} from './location';
import NearbyStops from './nearby-stops';
import {useChatTool} from './use-chat-tool';
import {BusFront,ArrowUp,Plus,LoaderCircle} from 'lucide-react';
type Reply={answer:string;cards?:Record<string,string|number>[];context?:Record<string,string>;mode?:string};
type Message=Reply & {role:'user'|'assistant'};
export default function Home(){
 const [messages,setMessages]=useState<Message[]>([]),[input,setInput]=useState(''),[busy,setBusy]=useState(false),[mapBusy,setMapBusy]=useState(false),[status,setStatus]=useState('Connecting'),[context,setContext]=useState<Record<string,string>>({});
 const [mapQuery,setMapQuery]=useState<{origin:string;destination:string;options?:Record<string,string>}>();
 const [locationFix,setLocationFix]=useState<LocationFix>();
 const [lastJourney,setLastJourney]=useState<MapResult|null>(null),[selectedRoute,setSelectedRoute]=useState(0);
 const bottom=useRef<HTMLDivElement>(null);
 useEffect(()=>{fetch('/api/health').then(r=>r.json() as Promise<{model_available:boolean}>).then(d=>setStatus(d.model_available?'Ready':'Limited mode')).catch(()=>setStatus('Backend offline'));},[]);
 useEffect(()=>{
  // Browser scroll return values must not become React effect cleanup values.
  bottom.current?.scrollIntoView({behavior:'smooth'});
 },[messages,busy,mapBusy]);
 async function send(text:string){
  if(!text.trim()||busy||mapBusy)return;
  const explanation=explainJourney(text,lastJourney,selectedRoute);
  if(explanation){setInput('');setMessages(m=>[...m,{role:'user',answer:text},{role:'assistant',answer:explanation}]);return;}
  setInput('');setMessages(m=>[...m,{role:'user',answer:text}]);setBusy(true);
  try{
   const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,context})});
   if(!r.ok)throw new Error();const d:Reply=await r.json();setContext(d.context||{});
   if(d.context?.intent==='route'&&d.context.origin&&d.context.destination){setLastJourney(null);setMapBusy(true);setMapQuery({origin:d.context.origin,destination:d.context.destination,options:d.context});}
   else setMessages(m=>[...m,{role:'assistant',...d}]);
   return d;
  }catch{setMessages(m=>[...m,{role:'assistant',answer:'The local backend is unavailable. Start the project services and try again.'}]);}
  finally{setBusy(false);}
 }
 function mapRequest(origin:string,destination:string){
  setLastJourney(null);setMapBusy(true);setMessages(m=>[...m,{role:'user',answer:`Find a bus journey from ${origin} to ${destination}`}]);setContext({intent:'route',origin,destination});
 }
 function mapReply(result:MapResult|null,error?:string){
  setMapBusy(false);setLastJourney(result);setSelectedRoute(0);
  if(!result){setMessages(m=>[...m,{role:'assistant',answer:error||'I could not complete the journey search. Please try another stop.'}]);return;}
  const text=result.source==='Location check'?result.notice:result.routes.length?`I found ${result.routes.length} bus option(s) from ${result.origin.name} to ${result.destination.name}.`:`I could not find a bus journey from ${result.origin.name} to ${result.destination.name}. ${result.source==='OneMap'?'Try another boarding stop or destination.':'I can only check direct buses and same-stop one-transfer journeys in your January 2026 data while OneMap is unavailable. A journey with transfers may still exist.'}`;
  setMessages(m=>[...m,{role:'assistant',answer:text,mode:result.source,cards:result.routes.map(r=>({Journey:r.label,...(r.minutes!==undefined?{'Estimated duration':`${r.minutes} minutes`}:{}),...(r.walk_m!==undefined?{'Walking':`${r.walk_m} m`}:{}),Steps:r.legs.map(l=>`${l.mode==='BUS'?'Bus '+l.service:'Walk'}: ${l.from} → ${l.to}`).join('\n')}))}]);
 }
 useChatTool(send);
 const waiting=busy||mapBusy;
 return <div className="shell"><aside>
  <Link className="brand" href="/"><span className="brand-icon"><BusFront size={23}/></span>Buswise</Link>
  <button className="new" onClick={()=>{setMessages([]);setContext({});setMapQuery(undefined);setLastJourney(null);setSelectedRoute(0);}} disabled={waiting}><Plus size={18}/>New chat</button>
  <section className="sidebar-welcome"><h2>Welcome aboard.</h2><p>Where will today take you?</p><p>Find a bus, plan your journey,<br/>and ask along the way.</p></section>
  <details className="dataset"><summary>About the data</summary><p>Routes from OneMap. When unavailable, searches use the January 2026 bus dataset.</p><small>Live arrivals are not available.</small></details><div className="privacy"><span className="dot"/>{status}</div>
 </aside><main><header><div><h1>Bus journeys</h1></div><span className="snapshot">Bus only</span></header>
 <div className="conversation"><JourneyMap onSelect={setSelectedRoute} locationFix={locationFix} onOrigin={value=>{setContext({intent:"route",origin:value});setInput(`From ${value} to `);}} query={mapQuery} onRequest={mapRequest} onReply={mapReply}/>
 {messages.length===0?<section className="welcome compact-welcome"><div className="suggestions">{['From Woodlands Int to Hougang Int','Which buses serve stop 66009?','Last bus 168 at Woodlands Int'].map(s=><button key={s} disabled={waiting} onClick={()=>{void send(s);}}>{s}</button>)}</div></section>:<div className="messages">{messages.map((m,i)=><article key={i} className={`message ${m.role}`}><div className="avatar">{m.role==='assistant'?<BusFront size={17}/>:'Y'}</div><div className="message-body"><div className="speaker">{m.role==='assistant'?'Buswise':'You'}{m.mode&&m.mode!=='model'&&m.mode!=='rules'&&<small>{m.mode}</small>}</div><p>{m.answer}</p>{m.cards?.map((c,j)=><div className="result-card" key={j}>{Object.entries(c).map(([k,v])=><div key={k}><span>{k}</span><strong>{v}</strong></div>)}</div>)}</div></article>)}</div>}
 {waiting&&<div className="thinking"><LoaderCircle size={16} className="spin"/>{mapBusy?'Finding buses…':'Thinking…'}</div>}<div ref={bottom}/></div>
 <footer><div className="composer-content"><NearbyStops onLocation={setLocationFix} disabled={waiting} onServices={code=>{void send(`Which buses serve stop ${code}?`);}} onOrigin={code=>{setContext({intent:'route',origin:code});setInput(`From ${code} to `);document.getElementById('question')?.focus();}}/><form className="chat-composer" onSubmit={e=>{e.preventDefault();void send(input);}}><label className="sr-only" htmlFor="question">Ask a bus route question</label><input id="question" value={input} onChange={e=>setInput(e.target.value)} maxLength={600} placeholder="Ask about your bus journey…" autoComplete="off"/><button aria-label="Send question" disabled={waiting||!input.trim()}><ArrowUp size={21}/></button></form></div></footer></main></div>;
}
