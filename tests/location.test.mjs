import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const exports={};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../app/location.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports});
const fix={coords:{latitude:1.436,longitude:103.786,accuracy:35}};
test('timeout retries precise location and returns fix',async()=>{
 let attempts=0,retries=0;
 const result=await exports.locateDevice({getCurrentPosition(ok,fail,options){attempts++;if(attempts===1)fail({code:3});else{assert.equal(options.enableHighAccuracy,true);ok(fix);}}},new AbortController().signal,()=>retries++);
 assert.equal(result.latitude,1.436);assert.equal(attempts,2);assert.equal(retries,1);
});
test('permission denied does not retry',async()=>{
 let attempts=0;
 await assert.rejects(exports.locateDevice({getCurrentPosition(ok,fail){attempts++;fail({code:1});}},new AbortController().signal,()=>{}),/permission is blocked/);
 assert.equal(attempts,1);
});
test('cancel ignores a late device fix',async()=>{
 const controller=new AbortController();let callback;
 const pending=exports.locateDevice({getCurrentPosition(ok){callback=ok;}},controller.signal,()=>{});
 controller.abort();callback(fix);
 await assert.rejects(pending,/cancelled/);
});
test('outside Singapore does not move map to unsupported coordinates',async()=>{
 await assert.rejects(exports.locateDevice({getCurrentPosition(ok){ok({coords:{latitude:51,longitude:0,accuracy:10}});}},new AbortController().signal,()=>{}),/outside Singapore/);
});
