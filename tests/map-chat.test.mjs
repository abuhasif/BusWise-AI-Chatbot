import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

for(const success of [true,false])test(`Find forwards ${success?'journey':'error'} to chat`,async()=>{
 const nodes=[],requests=[],replies=[];let state=0;
 const hooks={useEffect:()=>{},useRef:initial=>({current:initial}),useState:initial=>[state++===0?'Woodlands Int':state===2?'Hougang Int':initial,()=>{}]};
 const source=readFileSync(new URL('../app/journey-map.tsx',import.meta.url),'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 const exports={};const data=success?{source:'January 2026 database',routes:[],notice:'No direct route'}:{error:'Could not locate destination'};
 const jsx=(type,props)=>{const node={type,props};nodes.push(node);return node;};
 vm.runInNewContext(code,{exports,AbortController,fetch:async()=>({ok:success,json:async()=>data}),require:name=>name==='react'?hooks:name==='react/jsx-runtime'?{jsx,jsxs:jsx}:{}});
 exports.default({onRequest:(...args)=>requests.push(args),onReply:(...args)=>replies.push(args)});
 nodes.find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(requests.length,1);
 assert.equal(requests[0][0],'Woodlands Int');
 assert.equal(requests[0][1],'Hougang Int');
 assert.equal(replies.length,1);
 if(success)assert.equal(replies[0][0],data);
 else{assert.equal(replies[0][0],null);assert.equal(replies[0][1],data.error);}
});
