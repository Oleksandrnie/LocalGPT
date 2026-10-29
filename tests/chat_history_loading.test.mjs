import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync(new URL('../web_ui/js/app.js',import.meta.url),'utf8');
function install(context, name) {
  const start = source.indexOf(`async function ${name}(`);
  const end = source.indexOf('\n}',start)+2;
  vm.runInContext(source.slice(start,end),context);
}
function harness(request) {
  const state={activeProfileId:7,currentSessionId:null,messages:[],messageAttachments:{},chatAttachments:[],sessions:[],selectedLlmModel:'qwen3:8b'};
  const notices=[],renders=[];
  const context=vm.createContext({state,request, STORAGE_KEYS:{activeSessionId:'session',llmModel:'model'},
    els:{chatTitle:{},promptInput:{value:'synthetic request'}},writeStored(){},
    clearChatAttachments:async()=>{},renderMessages:()=>renders.push(state.messages.map(m=>m.content)),
    renderTranscriptStrip(){},renderSessionList(){},renderContextSummary(){},closeSidebar(){},
    applyCurrentSessionMeta(){},scrollMessagesToBottom(){},recoverActiveChatTaskFromMessages:async()=>{},
    setFooter:(...args)=>notices.push(args),readStored:()=>'',
    ensureModelInstalled:async()=>true,updateSendButtonState(){},renderChatAttachments(){},autoResizePrompt(){},
    activeProfileStreamingEnabled:()=>false,AbortController,AUTO_MODEL_ID:'auto',
    isAbortError:()=>false,closeChatTaskEventSource(){},clearChatTaskReplay(){},clearChatTypingStreams(){},
  });
  return {context,state,notices,renders};
}
const messages={messages:[{id:1,role:'user',content:'synthetic request'},{id:2,role:'assistant',content:'synthetic answer'}]};
test('auxiliary failure cannot hide persisted chat messages',async()=>{
  const h=harness(async path=>{if(path.includes('/messages?'))return messages;if(path.startsWith('/transcripts'))throw new Error('ASR unavailable');return {attachments:[]}});
  install(h.context,'openSession');await h.context.openSession('s1');
  assert.equal(h.state.messages.length,2);assert.equal(h.state.messages[1].content,'synthetic answer');
  assert.ok(h.notices.some(n=>n[1]==='warning'));
});
test('late session response cannot replace another chat',async()=>{
  let resolveA;const pending=new Promise(r=>resolveA=r);
  const h=harness(async path=>{if(path.includes('/a/messages'))return pending;if(path.includes('/b/messages'))return {messages:[{content:'B'}]};return {attachments:[],transcripts:[]}});
  install(h.context,'openSession');const a=h.context.openSession('a');await h.context.openSession('b');resolveA({messages:[{content:'A'}]});await a;
  assert.equal(h.state.currentSessionId,'b');assert.equal(h.state.messages[0].content,'B');
});
test('message refresh failure preserves same-session history',async()=>{
  const h=harness(async()=>{throw new Error('offline')});h.state.currentSessionId='s1';h.state.messages=messages.messages;
  install(h.context,'openSession');await h.context.openSession('s1');assert.equal(h.state.messages.length,2);
});
test('session list arriving after profile switch is ignored',async()=>{
  let resolve;const pending=new Promise(r=>resolve=r);const h=harness(()=>pending);
  install(h.context,'loadSessions');const load=h.context.loadSessions();h.state.activeProfileId=9;resolve({sessions:[{id:'private-to-old-profile'}]});await load;
  assert.equal(h.state.sessions.length,0);
});
test('pending request is displayed before slow task preparation finishes',async()=>{
  let resolve;const pending=new Promise(r=>resolve=r);const h=harness(()=>pending);
  h.context.loadSessions=async()=>{h.state.currentSessionId='s1';h.state.messages=messages.messages};
  install(h.context,'sendPromptText');const send=h.context.sendPromptText('synthetic request',{clearInput:true});
  await new Promise(r=>setImmediate(r));
  assert.equal(h.state.pendingChatMessage.content,'synthetic request');assert.equal(h.context.els.promptInput.value,'');
  resolve({id:'task',state:'completed',session_id:'s1',model_name:'qwen3:8b',user_message_id:1});await send;
  assert.equal(h.state.pendingChatMessage,null);assert.equal(h.state.messages.length,2);
});
test('failed task submission restores the cleared composer',async()=>{
  const h=harness(async()=>{throw new Error('preparation failed')});h.context.loadSessions=async()=>{};
  install(h.context,'sendPromptText');await h.context.sendPromptText('synthetic request',{clearInput:true});
  assert.equal(h.context.els.promptInput.value,'synthetic request');assert.equal(h.state.pendingChatMessage,null);
});

test('new chat and different session resume following while same-session refresh preserves pause',async()=>{
  const h=harness(async path=>path.includes('/messages?')?messages:{attachments:[],transcripts:[]});
  install(h.context,'openSession');
  h.state.currentSessionId='s1';h.state.autoScrollPinned=false;
  await h.context.openSession('s1');assert.equal(h.state.autoScrollPinned,false);
  await h.context.openSession('s2');assert.equal(h.state.autoScrollPinned,true);
  h.state.autoScrollPinned=false;await h.context.openSession(null);assert.equal(h.state.autoScrollPinned,true);
  h.state.autoScrollPinned=false;await h.context.openSession(null);assert.equal(h.state.autoScrollPinned,true);
});

test('profile navigation resumes following but refreshing the same profile preserves pause',async()=>{
  const h=harness(async()=>({}));
  Object.assign(h.context,{applyActiveProfilePreferences(){},renderProfileOptions(){},renderProfileManagement(){},
    loadSessions:async()=>{},loadAsrToolHistory:async()=>{},loadRagStatus:async()=>{},
    refreshModelSettings:async()=>{},refreshAsrPipelineSettings:async()=>{}});
  install(h.context,'setActiveProfile');
  h.state.autoScrollPinned=false;await h.context.setActiveProfile(7);assert.equal(h.state.autoScrollPinned,false);
  await h.context.setActiveProfile(9);assert.equal(h.state.autoScrollPinned,true);
});
