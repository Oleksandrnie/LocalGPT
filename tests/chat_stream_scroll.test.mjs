import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../web_ui/js/app.js',import.meta.url),'utf8');
function harness() {
 const frames=[];
 const scroll={scrollTop:320,scrollHeight:1800,clientHeight:500,scrollTo({top,behavior}) { assert.equal(behavior,'instant');this.scrollTop=top; }};
 const list={value:'',set innerHTML(value){this.value=value;scroll.scrollTop=0;},get innerHTML(){return this.value;}};
 const state={autoScrollPinned:false,messages:[{id:1,role:'assistant',status:'streaming',content:'Synthetic answer'}],messageAttachments:{}};
 const context=vm.createContext({state,els:{messageScroll:scroll,messageList:list,emptyState:{},scrollTopButton:{}},
 requestAnimationFrame:fn=>frames.push(fn),observeMessageScrollEnd(){},normalizeMessageStatus:m=>m.status,
 assistantStatusMeta:()=>({label:'Generating',text:'Generating'}),isAssistantMessageActive:()=>true,
 visionSourceUserMessageForIndex:()=>null,formatRichMessage:text=>text,escapeHtml:text=>String(text),formatDateTime:()=>''});
 for(const name of ['chatWaitingDotsMarkup','updateChatWaitingStatus','pendingChatContextMatches','assistantMessageMatchesPending','shouldShowPendingChatWaitingDots','shouldShowAssistantWaitingDots','renderMessages','pauseMessageAutoScroll','handleMessageScrollIntent','syncMessageScrollState','scrollMessagesToBottom']) {
  const start=source.indexOf(`function ${name}(`);
  vm.runInContext(source.slice(start,source.indexOf('\n}\n',start)+2),context);
 }
 return {state,scroll,list,context,flush(){while(frames.length)frames.shift()();}};
}
test('stream repaint preserves reader position and follows only when pinned',()=>{
 const h=harness();
 for(let i=0;i<20;i++){h.scroll.scrollHeight+=10;h.context.renderMessages();h.flush();assert.equal(h.scroll.scrollTop,320);assert.equal(h.state.autoScrollPinned,false);}
 h.state.autoScrollPinned=true;h.context.renderMessages();assert.equal(h.scroll.scrollTop,h.scroll.scrollHeight);
});
test('queued automatic scroll respects user movement before animation frame',()=>{
 const h=harness();h.state.autoScrollPinned=true;h.context.scrollMessagesToBottom();
 h.state.autoScrollPinned=false;h.scroll.scrollTop=150;h.flush();assert.equal(h.scroll.scrollTop,150);
 h.context.scrollMessagesToBottom({force:true});h.flush();assert.equal(h.scroll.scrollTop,h.scroll.scrollHeight);
});
test('old assistant transport output is not rendered or offered for copying',()=>{
 const h=harness();h.state.messages[0].content='[LOCALGPT_DATA_ENVELOPE trust_class=L4] private payload';
 h.context.renderMessages();assert.doesNotMatch(h.list.innerHTML,/LOCALGPT_DATA_ENVELOPE|private payload|data-copy-index/);
 assert.match(h.list.innerHTML,/служебный формат/);
 h.state.messages[0].role='user';h.context.renderMessages();assert.match(h.list.innerHTML,/LOCALGPT_DATA_ENVELOPE/);
});

test('small upward gesture pauses before native scroll and survives many near-bottom repaints',()=>{
 const h=harness();h.state.autoScrollPinned=true;h.context.renderMessages();h.flush();
 h.context.scrollMessagesToBottom({force:true});
 h.context.handleMessageScrollIntent(-1);
 // A repaint can run before the browser applies the wheel gesture.
 h.context.renderMessages();h.flush();assert.equal(h.state.autoScrollPinned,false);
 h.scroll.scrollTop=h.scroll.scrollHeight-h.scroll.clientHeight-8;
 const readingTop=h.scroll.scrollTop;
 for(let i=0;i<100;i++){h.scroll.scrollHeight+=1;h.context.renderMessages();h.flush();assert.equal(h.scroll.scrollTop,readingTop);assert.equal(h.state.autoScrollPinned,false);}
});
test('manual scrolling resumes only at actual bottom, including scrollbar movement before scroll event',()=>{
 const h=harness();h.context.syncMessageScrollState();
 h.scroll.scrollTop=1250;h.context.syncMessageScrollState({userScroll:true});
 assert.equal(h.state.autoScrollPinned,false); // within the former 96px threshold
 h.scroll.scrollTop=1299;h.context.renderMessages();h.flush();
 assert.equal(h.state.autoScrollPinned,true);
 h.scroll.scrollTop=1280;h.context.renderMessages();h.flush();
 assert.equal(h.state.autoScrollPinned,false);assert.equal(h.scroll.scrollTop,1280);
});
test('upward input cancels queued forced jump, while explicit later jump resumes following',()=>{
 const h=harness();h.context.scrollMessagesToBottom({force:true});
 h.context.handleMessageScrollIntent(-10);h.flush();assert.equal(h.scroll.scrollTop,320);
 h.context.scrollMessagesToBottom({force:true});h.flush();assert.equal(h.state.autoScrollPinned,true);
 h.scroll.scrollHeight+=100;h.context.renderMessages();assert.equal(h.scroll.scrollTop,h.scroll.scrollHeight);
});
test('completion and cancellation preserve manual scroll mode',()=>{
 const cancel=source.slice(source.indexOf('async function cancelCurrentChatGeneration('),source.indexOf('function insertPromptText('));
 assert.doesNotMatch(cancel,/scrollMessagesToBottom\(\{ force: true \}\)/);
 assert.match(source,/if \(shouldFollowCurrentContext\) scrollMessagesToBottom\(\);/);
});

test('downward gesture reaching current bottom resumes despite a moving native scroll target',()=>{
 const h=harness();h.context.syncMessageScrollState();
 h.context.handleMessageScrollIntent(20);assert.equal(h.state.autoScrollPinned,false);
 h.context.handleMessageScrollIntent(1000);assert.equal(h.state.autoScrollPinned,true);
 h.scroll.scrollHeight+=100;h.context.renderMessages();h.flush();assert.equal(h.scroll.scrollTop,h.scroll.scrollHeight);
});
