import test from 'node:test';
import assert from 'node:assert/strict';
import { waitForKnowledgeSearch } from '../web_ui/js/knowledge_search_client.mjs';
const running={task_id:'ks_synthetic',state:'running'};
function monitor(){let stopped=false;return {factory:()=>({stop(){stopped=true}}),get stopped(){return stopped}}}
test('polls scoped job while waiting confirmation is independent and returns saved result',async()=>{
 const calls=[], m=monitor();let polls=0;
 const result=await waitForKnowledgeSearch({body:{profile_id:7,session_id:'s1',query:'synthetic'},monitorFactory:m.factory,
  request:async(path)=>{calls.push(path);if(path.endsWith('/tasks'))return running;return ++polls===1?running:{...running,state:'completed',result:{reply:'evidence',session_id:'s1'}}},sleep:async()=>{}});
 assert.equal(result.reply,'evidence');assert.equal(polls,2);assert.ok(calls[1].includes('profile_id=7&session_id=s1'));assert.equal(m.stopped,true);
});
test('cancel during initial job start still obtains ID and cancels server without polling',async()=>{
 const controller=new AbortController(), calls=[],m=monitor();let resolve;
 const initial=new Promise(r=>resolve=r);
 const wait=waitForKnowledgeSearch({body:{profile_id:7,session_id:null},signal:controller.signal,monitorFactory:m.factory,
  request:async(path)=>{calls.push(path);return path.endsWith('/tasks')?initial:{...running,state:'cancelled'}},sleep:async()=>{}});
 controller.abort();resolve(running);
 await assert.rejects(wait,{name:'AbortError'});
 assert.equal(calls.length,2);assert.match(calls[1],/\/cancel\?profile_id=7$/);assert.equal(m.stopped,true);
});
test('pre-cancelled operation never starts a job',async()=>{
 const controller=new AbortController();controller.abort();let called=false;
 await assert.rejects(waitForKnowledgeSearch({body:{profile_id:7},signal:controller.signal,request:async()=>{called=true}}),{name:'AbortError'});
 assert.equal(called,false);
});
test('failed job is distinct from no matches and stops the monitor',async()=>{
 const m=monitor();
 await assert.rejects(waitForKnowledgeSearch({body:{profile_id:7},monitorFactory:m.factory,
 request:async()=>({...running,state:'failed',error:{status_code:503,detail:{message:'Embedding unavailable'}}})}),{message:'Embedding unavailable',status:503});
 assert.equal(m.stopped,true);
});
