import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

// Exercise the actual Home effect with both browser return conventions.
// A React effect must never expose the browser's Promise as its cleanup.
for (const returnsPromise of [false,true]) {
 test(`scroll effect returns no cleanup when browser returns ${returnsPromise?'a Promise':'undefined'}`,()=>{
  const effects=[];let scrolled=0;
  const hooks={useEffect:callback=>effects.push(callback),useRef:()=>({current:{scrollIntoView:()=>{scrolled++;return returnsPromise?Promise.resolve():undefined;}}}),useState:initial=>[initial,()=>{}]};
  const source=readFileSync(new URL('../app/page.tsx',import.meta.url),'utf8');
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const exports={};
  vm.runInNewContext(code,{exports,require:name=>name==='react'?hooks:name==='react/jsx-runtime'?{jsx:()=>null,jsxs:()=>null}:name.endsWith('use-chat-tool')?{useChatTool:()=>{}}:{default:()=>null}});
  exports.default();
  assert.equal(effects.length,2);
  assert.equal(effects[1](),undefined,'React must not receive a Promise as effect cleanup');
  assert.equal(scrolled,1);
 });
}
