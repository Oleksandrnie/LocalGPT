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
 for(const name of ['renderMessages','syncMessageScrollState','scrollMessagesToBottom']) {
  const start=source.indexOf(`function ${name}(`);
  vm.runInContext(source.slice(start,source.indexOf('\n}',start)+2),context);
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
