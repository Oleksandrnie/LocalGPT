import assert from "node:assert/strict";
import test from "node:test";

import { formatRichMessage } from "../web_ui/js/markdown.mjs";

test("ordered list numbering continues after blank lines and nested bullets", () => {
  const html = formatRichMessage(
    [
      "1. **Откройте папку в Google Drive**:",
      "",
      "- Перейдите в нужную папку.",
      "",
      "2. **Скопируйте URL папки**:",
      "",
      "- Откройте меню доступа.",
      "",
      "3. **Извлеките ID из URL**:",
      "",
      "- ID находится после `/folders/`.",
    ].join("\n"),
  );

  const orderedStarts = [...html.matchAll(/<ol class="message-md-list message-md-list--ordered"(?: start="(\d+)")?>/g)]
    .map((match) => match[1] || "1");

  assert.deepEqual(orderedStarts, ["1", "2", "3"]);
  assert.match(html, /<ol class="message-md-list message-md-list--ordered" start="2">/);
  assert.match(html, /<ol class="message-md-list message-md-list--ordered" start="3">/);
  assert.match(html, /<li><strong>Скопируйте URL папки<\/strong>:/);
});

test("code blocks are registered for copy buttons", () => {
  const blocks = [];
  const html = formatRichMessage("```js\nconsole.log('ok');\n```", {
    registerCodeBlock: (code) => {
      blocks.push(code);
      return blocks.length - 1;
    },
  });

  assert.deepEqual(blocks, ["console.log('ok');"]);
  assert.match(html, /data-code-copy-index="0"/);
  assert.match(html, /<span class="message-md-codeblock__lang">js<\/span>/);
});

test("model output is escaped instead of rendered as trusted HTML", () => {
  const html = formatRichMessage(
    '<img src=x onerror="globalThis.pwned=true"><script>alert(1)</script><a href="javascript:alert(2)">open</a>',
  );

  assert.doesNotMatch(html, /<script|<img|<a\s/i);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(html, /javascript:alert\(2\)/);
});

test("model output inside code blocks remains inert text", () => {
  const html = formatRichMessage("```html\n<script>fetch('/private')</script>\n```");

  assert.doesNotMatch(html, /<script>/i);
  assert.match(html, /&lt;script&gt;fetch\(&#39;\/private&#39;\)&lt;\/script&gt;/);
});
