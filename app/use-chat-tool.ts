import {useEffect,useRef} from 'react';
type ToolInput={question?:unknown};
type Context={registerTool:(tool:{name:string;description:string;inputSchema:object;annotations:object;execute:(input:ToolInput)=>Promise<unknown>},options:{signal:AbortSignal})=>void|Promise<void>};
export function useChatTool(send:(text:string)=>Promise<unknown>){
 const current=useRef(send);
 useEffect(()=>{current.current=send;});
 useEffect(()=>{
  const context=(document as Document & {modelContext?:Context}).modelContext;
  if(!context)return;
  const life=new AbortController();
  void Promise.resolve(context.registerTool({name:'ask_bus_question',description:'Ask the local bus assistant a route question and append the answer to the visible conversation. Uses a January 2026 snapshot, not live data.',inputSchema:{type:'object',properties:{question:{type:'string',minLength:1,maxLength:600}},required:['question'],additionalProperties:false},annotations:{readOnlyHint:false,untrustedContentHint:true},execute:async(input)=>{if(typeof input.question!=='string'||!input.question.trim()||input.question.length>600)throw new Error('Question must contain 1–600 characters');return await current.current(input.question);}}, {signal:life.signal})).catch(()=>{/* Optional browser API; chat remains available. */});
  return ()=>life.abort();
 },[]);
}
