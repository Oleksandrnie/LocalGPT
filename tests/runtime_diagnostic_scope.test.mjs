import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {attachRuntimeDiagnostics} from './helpers/runtime_diagnostics_harness.mjs';
const source=fs.readFileSync(new URL('../web_ui/js/app.js',import.meta.url),'utf8');
function setup(){const state={activeProfileId:3,currentSessionId:'new-session',selectedLlmModel:'new-model',modelSettingsState:{effective:{ollama_think:'on',output_tokens:4096,thinking_tokens:8192}},embeddingSetup:{profile_id:3,active:true,model:'embeddinggemma:latest',provider:{provider:'ollama'}}};const context=vm.createContext({state,activeProfileRagEnabled:()=>true});attachRuntimeDiagnostics(context,source);return {context,state};}
test('late task from another profile cannot inherit new profile settings or embedding state',()=>{
 const {context}=setup();const snapshot=context.runtimeDiagnosticContext({profile_id:2,session_id:'old-session',model:'old-model'});
 assert.equal(snapshot.profile_id,2);assert.equal(snapshot.session_id,'old-session');assert.equal(snapshot.thinking,null);assert.equal(snapshot.rag_context_enabled,null);assert.equal(snapshot.embedding_status,undefined);assert.equal(snapshot.output_tokens,undefined);
});
test('model switch in same profile retains profile metadata but no wrong model budgets',()=>{
 const {context}=setup();const snapshot=context.runtimeDiagnosticContext({model:'old-model'});
 assert.equal(snapshot.thinking,null);assert.equal(snapshot.output_tokens,undefined);assert.equal(snapshot.rag_context_enabled,true);assert.equal(snapshot.embedding_status,'ready');
});
test('snapshot keeps original operation settings after later UI changes',()=>{
 const {context,state}=setup();const snapshot=context.runtimeDiagnosticContext();state.activeProfileId=4;state.modelSettingsState.effective.ollama_think='off';
 assert.equal(snapshot.profile_id,3);assert.equal(snapshot.thinking,'on');assert.equal(snapshot.output_tokens,4096);
 const current=context.runtimeDiagnosticContext({profile_id:undefined,model:undefined});assert.equal(current.profile_id,4);assert.equal(current.model,'new-model');
});
