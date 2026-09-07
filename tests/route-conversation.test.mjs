import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const exports={};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../app/route-conversation.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports});
test('second route explanation uses saved legs and duration',()=>{
 const result={routes:[{label:'161',legs:[]},{label:'168 -> 88',minutes:72,legs:[{mode:'BUS',service:'168',from:'Woodlands',to:'Transfer stop'},{mode:'BUS',service:'88',from:'Transfer stop',to:'Pasir Ris'}]}]};
 const text=exports.explainJourney('Where do I change for the second route?',result);
 assert.match(text,/Transfer stop/);assert.match(text,/72 minutes/);assert.match(text,/bus 88/);
 assert.match(exports.explainJourney('Explain the third route',result),/There are 2 options/);
 assert.equal(exports.explainJourney('From Woodlands to Hougang',result),null);
});
