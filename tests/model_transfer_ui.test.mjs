import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const html = fs.readFileSync(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const js = fs.readFileSync(new URL("../web_ui/js/app.js", import.meta.url), "utf8");
const css = fs.readFileSync(new URL("../web_ui/css/style.css", import.meta.url), "utf8");

test("System settings expose model export and import controls", () => {
  for (const id of ["modelTransferList", "exportModelsButton", "importModelsButton", "importModelsInput", "modelTransferStatus"]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /accept="\.localgpt-models"/);
});

test("UI performs preview, export, inspect, confirmation, and apply", () => {
  for (const contract of [
    "/model-transfer/export-preview",
    "/model-transfer/exports",
    "/model-transfer/import-inspect",
    "/model-transfer/imports",
    "openConfirmDialog",
  ]) {
    assert.ok(js.includes(contract), `missing ${contract}`);
  }
  assert.match(css, /\.model-transfer__item/);
});
