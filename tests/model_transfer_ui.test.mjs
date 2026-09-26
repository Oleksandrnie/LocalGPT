import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const html = fs.readFileSync(new URL("../web_ui/gui_html.html", import.meta.url), "utf8");
const js = fs.readFileSync(new URL("../web_ui/js/app.js", import.meta.url), "utf8");
const css = fs.readFileSync(new URL("../web_ui/css/style.css", import.meta.url), "utf8");

test("System settings expose model export and import controls", () => {
  for (const id of [
    "exportModelsButton",
    "importModelsButton",
    "importModelsInput",
    "modelTransferStatus",
    "modelExportBackdrop",
    "modelTransferList",
    "selectAllModelExportInput",
    "confirmModelExportButton",
    "modelTransferUploadsSummary",
    "cleanupModelTransferUploadsButton",
  ]) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /accept="\.localgpt-models"/);
  assert.ok(
    html.indexOf('id="modelTransferList"') > html.indexOf('id="modelExportBackdrop"'),
    "model selection list must live inside the export modal",
  );
});

test("UI performs preview, export, inspect, confirmation, and apply", () => {
  for (const contract of [
    "/model-transfer/export-preview",
    "/model-transfer/exports",
    "/model-transfer/import-inspect",
    "/model-transfer/imports",
    "/model-transfer/uploads",
    "openConfirmDialog",
  ]) {
    assert.ok(js.includes(contract), `missing ${contract}`);
  }
  assert.match(css, /\.model-transfer__item/);
  assert.match(css, /\.model-transfer \[hidden\]/);
  assert.match(js, /formatModelTransferRuntimeRequirements/);
  assert.match(js, /Проверьте локальные runtime/);
  assert.match(html, /Bundle переносит веса и provider-данные/);
});

test("System settings load the model inventory automatically", () => {
  assert.match(js, /if \(next === "system"\) \{\s*ensureModelTransferPreview\(\);/);
  assert.match(js, /if \(next === "system"\) \{\s*ensureModelTransferPreview\(\);\s*ensureModelTransferUploads\(\);/);
  assert.match(js, /if \(state\.activeSettingsTab === "system"\) \{\s*ensureModelTransferPreview\(\);/);
  assert.match(js, /modelTransferPreviewLoaded: false/);
});

test("System settings show and confirm cleanup of temporary import archives", () => {
  assert.match(js, /cleanupModelTransferUploadsButton\?\.addEventListener\("click", \(\) => void cleanupModelTransferUploads\(\)\)/);
  assert.match(js, /confirmLabel: "Удалить архивы"/);
  assert.match(js, /method: "DELETE"/);
  assert.match(css, /\.model-transfer__uploads/);
});

test("Export opens a selection modal and only its confirmation starts the task", () => {
  assert.match(js, /exportModelsButton\?\.addEventListener\("click", openModelExportDialog\)/);
  assert.match(js, /confirmModelExportButton\?\.addEventListener\("click", \(\) => void startModelExport\(\)\)/);
  assert.match(js, /selectAllModelExportInput\?\.addEventListener\("change"/);
  assert.match(js, /if \(!els\.modelExportBackdrop\?\.hidden\) \{\s*closeModelExportDialog\(\);/);
  assert.match(css, /#modelExportBackdrop/);
  assert.match(css, /\.model-export-dialog__content/);
});
