import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const script = fs.readFileSync(new URL("../web_ui/js/app.js", import.meta.url), "utf8");

assert.match(html, /id="memTurnsInput"[^>]*min="0"[^>]*max="100"/);
assert.match(html, /Одна пара — сообщение пользователя и завершённый ответ ассистента/);
assert.match(script, /messages\?profile_id=/);
assert.match(script, /reasoning\?profile_id=.*session_id=/);
assert.match(script, /rag\/status.*session_id=/s);
assert.match(script, /Число последних завершённых пар user \+ assistant только из текущего чата/);

console.log("✔ profile/session UI requests and history-turn semantics are explicit");
