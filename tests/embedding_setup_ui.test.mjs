import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../web_ui/js/app.js',import.meta.url),'utf8');
function harness(request, approve=true){
 const state={activeProfileId:7,ragStatus:{embedding:{provider:'local_hash'}}},calls=[],dialogs=[],store=new Map();
 const element=()=>({hidden:false,textContent:'',removeAttribute(){}});
 const els={embeddingSetupAction:element(),embeddingSetupDetails:element(),embeddingSetupProgress:element(),embeddingSetupLexical:element(),promptInput:{value:''}};
 const context=vm.createContext({state,els,window:{clearTimeout(){},setTimeout(){return 1}},
 request:async(path,args)=>{calls.push({path,args});return request(path,args)},setFooter(){},
 openConfirmDialog:async options=>{dialogs.push(options);return approve},loadRagStatus:async()=>{},
 openRagPanel:async()=>{},pollRagReindexTask(){},readStored:k=>store.get(k),writeStored:(k,v)=>store.set(k,v)});
 for(const name of ['renderEmbeddingSetup','loadEmbeddingSetup','runEmbeddingSetup','offerEmbeddingSetup']){
  const a=source.indexOf(`function ${name}(`),async=source.slice(a-6,a)==='async ';
  vm.runInContext((async?'async ':'')+source.slice(a,source.indexOf('\n}\n',a)+2),context);
 }
 return {state,els,context,calls,dialogs};
}
const missing={profile_id:7,model:'synthetic-embed',installed:false,active:false};
test('missing weights are installed only after user confirmation, without changing another profile',async()=>{
 const h=harness(async()=>missing,false);await h.context.runEmbeddingSetup();
 assert.equal(h.calls.length,1);assert.equal(h.dialogs.length,1);
 const yes=harness(async()=>missing);await yes.context.runEmbeddingSetup();
 assert.ok(yes.calls.some(c=>c.path==='/rag/embedding-setup/install?profile_id=7'&&c.args.method==='POST'));
 assert.equal(yes.state.embeddingSetupBusy,false);
});
test('installed weights offer profile reindex instead of another download',async()=>{
 const h=harness(async path=>path.includes('/activate')?{task_id:'reindex'}:{...missing,installed:true});
 await h.context.runEmbeddingSetup();
 assert.ok(h.calls.some(c=>c.path.includes('/activate?profile_id=7')));
 assert.ok(!h.calls.some(c=>c.path.includes('/install?')));
 assert.match(h.dialogs[0].message,/только для текущего профиля/);
});
test('late setup result cannot overwrite UI for another profile',async()=>{
 let resolve;const h=harness(()=>new Promise(r=>resolve=r));const pending=h.context.loadEmbeddingSetup();
 h.state.activeProfileId=8;resolve(missing);assert.equal(await pending,null);assert.equal(h.state.embeddingSetup,undefined);
});
test('startup proposal is offered once and does not interrupt typing or active work',async()=>{
 const h=harness(async()=>missing,false);
 h.els.promptInput.value='draft';await h.context.offerEmbeddingSetup();assert.equal(h.dialogs.length,0);
 h.els.promptInput.value='';h.state.isSending=true;await h.context.offerEmbeddingSetup();assert.equal(h.dialogs.length,0);
 h.state.isSending=false;await h.context.offerEmbeddingSetup();await h.context.offerEmbeddingSetup();
 assert.equal(h.dialogs.length,1);assert.ok(!h.calls.some(c=>c.args?.method==='POST'));
});
test('download progress and failure are shown rather than ready state',()=>{
 const h=harness(async()=>missing);h.state.embeddingSetup={...missing,download:{state:'running',total:100,completed:42}};
 h.context.renderEmbeddingSetup();assert.equal(h.els.embeddingSetupAction.disabled,true);assert.equal(h.els.embeddingSetupProgress.value,42);
 h.state.embeddingSetup.download={state:'error',message:'synthetic failed'};h.context.renderEmbeddingSetup();
 assert.match(h.els.embeddingSetupDetails.textContent,/synthetic failed/);assert.equal(h.els.embeddingSetupAction.disabled,false);
});
