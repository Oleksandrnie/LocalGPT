import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../web_ui/js/app.js',import.meta.url),'utf8');
function setup(){
 const state={confirmResolver:null}, operation={},calls=[];
 const context=vm.createContext({state,els:{promptInput:{}},openConfirmDialog:options=>{
  calls.push(options);return new Promise(resolve=>{state.confirmResolver=resolve})},
  resolveConfirmDialog:answer=>{const resolve=state.confirmResolver;state.confirmResolver=null;resolve(answer)}});
 for(const name of ['askKnowledgeSearchContinue','closeKnowledgeSearchWaitDialog']){
  const start=source.indexOf(`function ${name}(`);vm.runInContext(source.slice(start,source.indexOf('\n}\n',start)+2),context);
 }
 return {state,operation,calls,context};
}
test('search completion closes only its own pending confirmation without cancellation',async()=>{
 const h=setup(),answer=h.context.askKnowledgeSearchContinue(h.operation,()=>true);
 assert.equal(h.calls[0].confirmLabel,'Продолжить поиск');
 assert.equal(h.calls[0].cancelLabel,'Отменить поиск');
 h.context.closeKnowledgeSearchWaitDialog(h.operation);
 assert.equal(await answer,true);assert.equal(h.state.confirmResolver,null);
});
test('another confirmation or stale request is never replaced by search timer',async()=>{
 const h=setup();const owner=()=>{};h.state.confirmResolver=owner;
 assert.equal(await h.context.askKnowledgeSearchContinue(h.operation,()=>true),null);
 h.operation.waitDialogResolver=()=>{};h.context.closeKnowledgeSearchWaitDialog(h.operation);
 assert.equal(h.state.confirmResolver,owner);assert.equal(h.calls.length,0);
 h.state.confirmResolver=null;
 assert.equal(await h.context.askKnowledgeSearchContinue(h.operation,()=>false),null);
 assert.equal(h.calls.length,0);
});
test('dialog replacement is deferred rather than treated as user cancellation',async()=>{
 const h=setup();const answer=h.context.askKnowledgeSearchContinue(h.operation,()=>true);
 const old=h.state.confirmResolver;old(false);const other=()=>{};h.state.confirmResolver=other;
 assert.equal(await answer,null);assert.equal(h.state.confirmResolver,other);
});
