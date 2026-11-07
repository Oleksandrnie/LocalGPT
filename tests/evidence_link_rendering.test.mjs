import test from 'node:test';
import assert from 'node:assert/strict';
import { formatRichMessage } from '../web_ui/js/markdown.mjs';
test('requested HTTPS and local evidence links are clickable with escaped attributes',()=>{
 const html=formatRichMessage('[Telegram](https://t.me/example_chat/42) [Local](/rag/evidence/1?profile_id=2&session_id=s)');
 assert.match(html,/href="https:\/\/t.me\/example_chat\/42"/);
 assert.match(html,/href="\/rag\/evidence\/1\?profile_id=2&amp;session_id=s"/);
 assert.match(html,/rel="noopener noreferrer"/);
});
test('unsafe links, HTML and links inside citations remain inert',()=>{
 for(const url of ['javascript:alert(1)','data:text/html,x','https://user:pass@evil.invalid/x','//evil.invalid','/admin']) {
  assert.doesNotMatch(formatRichMessage(`[bad](${url})`),/<a /);
 }
 assert.doesNotMatch(formatRichMessage('`[code](https://example.invalid)`'),/<a /);
 const html=formatRichMessage('````text\n<script>bad()</script>\n```\n[quoted](https://example.invalid)\n````\n[Local](/rag/evidence/1?profile_id=2)');
 assert.match(html,/&lt;script&gt;/);
 assert.equal((html.match(/<a /g)||[]).length,1);
 assert.match(html,/\[quoted\]\(https:\/\/example.invalid\)/);
});
