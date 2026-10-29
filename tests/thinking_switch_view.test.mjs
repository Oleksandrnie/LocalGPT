import test from 'node:test';
import assert from 'node:assert/strict';
import { renderThinkingSegments } from '../web_ui/js/thinking_switch_view.mjs';
const levels=['low','medium','high'].map(value=>({value,label:value}));
test('three declared levels have three exact radio choices and a middle indicator',()=>{
 const html=renderThinkingSegments(levels,'medium');
 assert.equal((html.match(/role="radio"/g)||[]).length,3);
 assert.equal((html.match(/aria-checked="true"/g)||[]).length,1);
 assert.match(html,/--thinking-segment-count:3;--thinking-selected-index:1/);
 assert.match(html,/data-thinking-mode="medium"[^>]*aria-checked="true"/);
});
test('Auto does not falsely select the first model level',()=>{
 const html=renderThinkingSegments(levels,'auto');
 assert.doesNotMatch(html,/aria-checked="true"/);
 assert.match(html,/--thinking-has-selection:0/);
 assert.equal((html.match(/tabindex="0"/g)||[]).length,1);
});
test('binary controls and arbitrary names remain exact and safely escaped',()=>{
 const html=renderThinkingSegments([{value:'off',label:'Off'},{value:'on',label:'On'}],'on',true);
 assert.equal((html.match(/role="radio"/g)||[]).length,2);
 assert.equal((html.match(/ disabled /g)||[]).length,2);
 assert.match(renderThinkingSegments([{value:'X"<',label:'<script>'}],'X"<'),/X&amp;|X&quot;&lt;/);
 assert.doesNotMatch(renderThinkingSegments([{value:'x',label:'<script>'}],'x'),/<script>/);
});
test('Auto is a real first position beside both boolean runtime choices',()=>{
 const html=renderThinkingSegments([{value:'auto',label:'Auto'},{value:'on',label:'On'},{value:'off',label:'Off'}],'auto');
 assert.equal((html.match(/role="radio"/g)||[]).length,3);
 assert.equal((html.match(/aria-checked="true"/g)||[]).length,1);
 assert.match(html,/data-thinking-mode="auto"[^>]*aria-checked="true"/);
 assert.match(html,/--thinking-segment-count:3;--thinking-selected-index:0;--thinking-has-selection:1/);
});
