import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync("web_ui/gui_html.html", "utf8");
const script = fs.readFileSync("web_ui/js/app.js", "utf8");

assert.match(html, /id="downloadCaddyCertificateIosButton"/);
assert.match(html, /id="downloadCaddyCertificateAndroidButton"/);
assert.match(html, /Файл <code>root\.crt<\/code> сохраняется на этом компьютере/);
assert.match(script, /function downloadCaddyRootCertificate\(platform\)/);
assert.match(script, /link\.href = "\/network\/caddy\/root-ca"/);
assert.match(script, /downloadCaddyCertificateIosButton\.disabled = !state\.lanUrl/);
assert.match(script, /downloadCaddyCertificateAndroidButton\.disabled = !state\.lanUrl/);
assert.match(script, /downloadCaddyRootCertificate\("ios"\)/);
assert.match(script, /downloadCaddyRootCertificate\("android"\)/);

console.log("✔ LAN certificate controls download the guarded public root CA for both device types");
