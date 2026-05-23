# Mobile UI Progress

## Goal
Полноценная mobile-first адаптация static Web UI LocalGPT для экранов от iPhone SE до Pro Max / крупных Android, включая доступ через Tailscale, без нового UI-фреймворка и без отдельной mobile-страницы.

# Implementation Stages

## Stage 1 — Responsive Foundation
- [x] Status: completed.
- [x] Scope: responsive breakpoint variables, core layout normalization, safe-area token setup, `dvh/svh` migration for shell sizing.
- [x] Related files: `web_ui/css/style.css`, `documentation/progress/mobile-ui-progress.md`.
- [x] Local QA: static grep removed active `height: 100vh`, active `overflow-x: hidden`, and legacy `max-width: 980px` mobile breakpoint usage.

## Stage 2 — Mobile Sidebar
- [x] Status: completed.
- [x] Scope: off-canvas drawer, overlay, burger button state, repeat-tap close, Esc close, body scroll lock, desktop sidebar preference isolation.
- [x] Related files: `web_ui/gui_html.html`, `web_ui/css/style.css`, `web_ui/js/app.js`, `documentation/progress/mobile-ui-progress.md`.
- [x] Local QA: `node --check web_ui/js/app.js`; static grep for deprecated mobile patterns.

## Stage 3 — Topbar Refactor
- [x] Status: completed.
- [x] Scope: compact single-row layout, icon-only 44px controls, safe-area top padding, no mobile header growth, preserved network address behavior.
- [x] Related files: `web_ui/gui_html.html`, `web_ui/css/style.css`, `web_ui/js/app.js`, `documentation/progress/mobile-ui-progress.md`.
- [x] Local QA: `node --check web_ui/js/app.js`; static grep for numeric z-index and legacy mobile rules.

## Stage 4 — Chat Composer
- [x] Status: completed.
- [x] Scope: textarea adaptation, icon-only send/stop, `+` overflow menu touch targets, ASR dictation button sizing, OCR attach flow preservation, software keyboard behavior.
- [x] Related files: `web_ui/css/style.css`, `web_ui/js/app.js`, `documentation/progress/mobile-ui-progress.md`.
- [x] Local QA: Chrome CDP viewport metrics for 375x667, 390x844, 412x915, 430x932, 480x900, 667x375, and 1440x900; no horizontal overflow found.
- [x] Local QA: composer menu opens/closes by outside tap, menu items are 44px high, send button keeps accessible labels, mobile drawer body scroll lock still works.
- [x] Local QA: reduced-height 375x420 viewport kept composer visible; `node --check web_ui/js/app.js` passed; static grep found no active legacy `100vh`, `overflow-x: hidden`, numeric z-index, or `max-width: 980px` mobile rules.

## Stage 5 — Settings Mobile UI
- [x] Status: completed.
- [x] Scope: full-screen modal or bottom-sheet behavior, responsive tabs/sections, mobile-friendly forms, checkbox cards, plugin cards, model settings, internal scroll behavior.
- [x] Related files: `web_ui/css/style.css`, `web_ui/js/app.js`, `backend/apps/plugins/registry.py`, `backend/apps/plugins/routes.py`, `tests/test_plugin_registry.py`, `documentation/progress/mobile-ui-progress.md`.
- [x] Local QA: local-server Chrome pass at 375x667, 390x844, 412x915, 430x932, 667x375, 844x390, reduced-height 375x420, and 1440x900 across dark/light for profile, models, ASR, TTS, plugins, and system tabs; 96 checks passed with no horizontal overflow, no visible native select, no sub-44px mobile targets, active tabs visible, body scroll lock active on mobile, and clean desktop bounds.
- [x] Follow-up QA: plugin docs pills are now real links to a safe markdown endpoint; focused local-server Chrome check at 375x667 verified 44px mobile doc links with no overflow, and registry unit tests verified docs URL/read behavior plus traversal rejection.

## Stage 6 — ASR/TTS/OCR Mobile
- [x] Status: completed.
- [x] Scope: ASR Studio and TTS Voice Studio single-column layout, full-width controls, `AppSelect` preservation, history/cards without horizontal overflow, touch-friendly action buttons, OCR editor mobile behavior.
- [x] Related files: `web_ui/css/style.css`, `web_ui/js/app.js`, `web_ui/gui_html.html`, `documentation/progress/mobile-ui-progress.md`.
- [x] Local QA: TTS Voice Studio Chrome CDP viewport metrics for 375x667, 390x844, 412x915, 430x932, 667x375 landscape, and 1440x900 desktop.
- [x] Current sub-scope: fixed TTS Voice Studio mobile overlap only; ASR/OCR remain pending within Stage 6.
- [x] Current sub-scope: added explicit ASR transcript textarea/editor and kept export/chat/context actions on the same `#asrToolOutput` source.
- [x] Local QA: ASR Studio headless Chrome file-based geometry checks for 375x667, 390x844, 412x915, 430x932, 667x375 landscape, and 1440x900 desktop; no backend/model server started.
- [x] Current sub-scope: reduced ASR/TTS tool window transparency so the main page does not bleed through while reading.
- [x] Local QA: computed ASR/TTS tool window backgrounds are opaque `rgb(...)` in dark and light themes; no backend/model server started.
- [x] Current sub-scope: adapted OCR attach/editor mobile layout, removed overlap/overflow, preserved attach flow and editor actions.
- [x] Local QA: OCR editor headless Chrome file-based geometry checks for 375x667, 390x844, 412x915, 430x932, 667x375 landscape, reduced-height 375x420 keyboard simulation, and 1440x900 desktop; no backend/model server started.
- [x] Current sub-scope: final ASR/TTS/OCR cleanup normalized mobile tool-window safe-area bounds, ASR workflow text clamping, OCR opaque panel theme surfaces, and ASR/TTS mobile body scroll lock.
- [x] Local QA: final local-server Chrome pass at 375x667, 390x844, 412x915, 430x932, 667x375 landscape, reduced-height 375x420, and 1440x900 desktop across dark/light for ASR, TTS, and OCR; 42 checks passed with no horizontal overflow, no visible native select, no sub-44px mobile targets, opaque root surfaces, and clean desktop bounds.

## Stage 7 — QA + Cleanup
- [~] Status: in progress; Settings icon visual cleanup completed, final QA/cleanup remains.
- [ ] Scope: Settings icon visual cleanup, final automated viewport/theme QA, desktop regression pass, final static grep, safe cleanup of legacy responsive CSS/JS, real-device/Tailscale validation notes, temporary progress file deletion after completion.
- [x] Related files: `web_ui/gui_html.html`, `web_ui/css/style.css`, `web_ui/js/app.js`, `documentation/progress/mobile-ui-progress.md`.
- [~] Local QA: Settings icon local-server Chrome geometry/screenshot pass completed at 375x667, 430x932, and 1440x900 in dark/light; broader automated viewport pass, desktop regression pass, and final static grep remain.

## Completed
- [x] Scoped the work to the active static UI in `web_ui/`.
- [x] Identified the live UI entry points: `web_ui/gui_html.html`, `web_ui/css/style.css`, and `web_ui/js/app.js`.
- [x] Confirmed the existing code already uses custom `AppSelect` controls for native `<select>` elements.
- [x] Added responsive breakpoint variables for compact, phone, large phone, and tablet/small landscape ranges.
- [x] Added safe-area CSS variables for top, right, bottom, and left insets.
- [x] Switched core shell sizing to dynamic viewport height with `100svh` fallback.
- [x] Implemented mobile sidebar drawer with overlay, transient mobile state, repeat-tap close, and Esc close through the existing global handler.
- [x] Added body scroll lock for mobile drawer/settings overlays.
- [x] Reworked mobile topbar into a fixed-height single-row layout with 44px touch targets and no header growth.
- [x] Centralized z-index values into semantic CSS variables.
- [x] Removed legacy active mobile breakpoint `max-width: 980px`, direct `height: 100vh`, ad hoc numeric z-indexes, and active `overflow-x: hidden` rules.
- [x] Stage 2 test pass: `node --check web_ui/js/app.js` and static grep for deprecated mobile patterns.
- [x] Stage 3 topbar pass: single-row mobile topbar, safe-area top padding, 44px icon controls, and preserved LAN address copy/menu behavior.
- [x] Stage 4 composer pass: mobile composer uses 44px columns for `+` and send/stop, textarea reserves mic space, `+` menu items are touch-safe, outside tap closes menus, reduced-height viewport keeps composer accessible.
- [x] Stage 6a TTS Voice Studio pass: mobile layout is single-column, action/history sections no longer overlap, custom `AppSelect` remains active, and mobile touch targets are 44px.
- [x] Stage 6b ASR Studio editor pass: transcript text is now an explicit labelled textarea, mobile flow has one internal scroll region, and ASR buttons/selectors keep 44px mobile targets.
- [x] Stage 6c OCR editor pass: OCR modal is scoped to safe-area mobile layout, textarea/actions do not overlap, body scroll lock stays active, and OCR attach/editor actions keep the same JS flow.
- [x] Stage 6 final cleanup pass: ASR/TTS mobile windows lock body scroll while open, mobile tool windows use safe-area bounds without inherited desktop max constraints, ASR workflow labels clamp instead of overflowing on 375px, and OCR editor surfaces are opaque in dark/light.
- [x] Post-Stage 6 composer action menu opacity fix: `+` menu surface is now opaque in dark and light themes while preserving the existing mobile action flow.
- [x] Stage 5 Settings pass: mobile Settings now uses a safe-area modal shell with one internal scroll region, touch-safe horizontal tabs, single-column mobile forms, responsive model/library controls, wrapped plugin cards/runtime metadata, full-width plugin toggles, and 44px controls including ASR pipeline settings.
- [x] Post-Stage 5 plugin docs access fix: Settings plugin docs pills now open manifest-listed markdown files through a safe backend endpoint; missing docs remain muted, and mobile doc links keep 44px touch targets.
- [x] Stage 7 Settings icon cleanup: replaced the crooked gear with a centered controls/sliders icon from the visual brief, using three continuous horizontal lines, hollow knobs, and a lighter 1.6px Settings-only stroke.

## In Progress
- [~] Stage 7 QA + Cleanup: Settings icon is fixed and logged; next task is the broader final QA/static cleanup pass.

## Pending
- [ ] Stage 7: settings icon QA, dark/light theme pass, viewport QA, cleanup, real-device/Tailscale notes, and progress file deletion.

## Architecture Decisions
- The active UI is a static single-page app; no separate mobile page or UI framework will be added.
- Existing desktop sidebar state uses `sidebar_open` in localStorage. Mobile drawer state remains transient so desktop preference is preserved.
- The HTML already has `viewport-fit=cover`; CSS exposes safe-area tokens, and sidebar/topbar consume them.
- The mobile breakpoint system uses CSS variables at `<=390`, `391-430`, `431-480`, and `481-768`, plus a landscape-height media query for small landscape devices.
- Native selects remain hidden and upgraded through `AppSelect`; responsive work must keep that path intact.
- Touch targets must resolve to at least 44x44px on mobile, with hover-only affordances backed by tap/focus states.
- Mobile overlays must lock body scroll while allowing exactly one predictable internal scroll region.
- z-index changes use semantic CSS variables instead of ad hoc large values.
- Existing desktop drag/dropdown code uses inline positioning for desktop surfaces; no new inline mobile styles were added in Stages 1-2.
- Stages must remain separate: Settings/plugins are Stage 5; ASR/TTS/OCR Studio layout is Stage 6.
- Voice Studio mobile uses one predictable internal scroll region on `.tool-window__body`; panel/sidebar/history do not create nested vertical scroll.
- Voice Studio does not auto-focus the textarea on mobile, avoiding iOS software-keyboard resize jumps; desktop focus behavior is preserved.
- Mobile tool windows consume safe-area offsets and `--viewport-height`; the mobile `!important` overrides exist to beat persisted desktop inline drag/resize bounds.
- Mobile tool windows explicitly clear inherited desktop `max-width`/`max-height` constraints so safe-area `left/right/top/bottom` offsets define the actual mobile bounds.
- ASR Studio reuses the existing `#asrToolOutput` textarea as the single source for save/download/copy/prompt/chat actions; no duplicate mobile transcript component was added.
- ASR Studio mobile uses flex-based vertical flow inside `.tool-window__body` so tab content contributes real height and cannot overlap action/history sections.
- ASR/TTS tool windows now use semantic `--tool-window-bg` and `--tool-window-header-bg` tokens instead of translucent page-bleed backgrounds.
- OCR editor reuses the existing `#ocrTextOutput` textarea as the single source for insert/send/clear actions; scoped `#ocrBackdrop` mobile rules avoid changing Stage 5 Settings.
- OCR modal uses safe-area insets, body scroll lock, opaque tool-window surface tokens, and a reduced-height path for landscape/software-keyboard behavior.
- ASR/TTS mobile tool windows participate in the same body scroll lock as mobile drawers/modals while desktop tool windows remain unlocked and JS-positioned.
- Plugin docs are still metadata/docs-only: the UI links only to files listed in `plugin.json`, and the backend endpoint rejects missing, unlisted, unsafe, or non-UTF-8 docs without importing or executing plugin code.

## Changed Files
- `documentation/progress/mobile-ui-progress.md`
- `backend/apps/plugins/registry.py`
- `backend/apps/plugins/routes.py`
- `tests/test_plugin_registry.py`
- `web_ui/css/style.css`
- `web_ui/js/app.js`
- `web_ui/gui_html.html`

## Known Issues / Technical Debt
- [ ] ASR Studio mobile remains content-heavy and long-scroll by design for now; later Stage 6 cleanup can compact secondary action groups if needed.
- [ ] Real iOS Safari, Android Chrome, and slow Tailscale checks cannot be completed from this machine alone and need device validation.

## QA Checklist
- [x] 375x667 iPhone SE viewport
- [x] 390x844 iPhone 12/13/14 viewport
- [x] 430x932 iPhone Pro Max viewport
- [x] 412x915 Android viewport
- [x] Landscape mobile viewport
- [x] TTS Voice Studio mobile viewport pass: no overlap, no horizontal scroll, 44px mobile targets, custom selects hidden/native selects not visible.
- [x] ASR Studio mobile viewport pass: explicit transcript textarea visible, no overlap, no horizontal scroll, 44px mobile targets.
- [x] ASR/TTS opacity pass: opaque tool window surfaces verified in dark and light themes.
- [x] OCR editor mobile viewport pass: no overlap, no horizontal scroll, 44px mobile targets, body scroll lock, reduced-height keyboard simulation.
- [x] Dark theme mobile pass
- [x] Light theme mobile pass
- [x] Composer `+` action menu opacity pass in dark/light themes.
- [x] Stage 5 Settings mobile pass: 96 local-server Chrome checks across mobile/landscape/reduced-height/desktop, dark/light, all Settings tabs, synthetic long plugin card, and expanded ASR pipeline controls.
- [x] Stage 5 plugin docs access pass: `venv/bin/python -m unittest tests.test_plugin_registry -q`, plugin docs endpoint smoke check, and focused 375x667 local-server Chrome check for clickable 44px docs links.
- [x] Stage 7 Settings icon pass: local-server Chrome geometry/screenshot check at 375x667, 430x932, and 1440x900 in dark/light verified the full-line/hollow-knob icon, centered SVG, mobile 44px target, and no horizontal overflow.
- [x] Desktop visual regression pass for topbar/composer metrics
- [x] Stage 6 desktop regression pass for ASR/TTS/OCR tool windows
- [ ] Real iOS Safari device check
- [ ] Real Android Chrome device check
- [ ] Slow Tailscale connection behavior check

## Next Steps
- [x] Fix TTS Voice Studio mobile overlap and run viewport QA.
- [x] Add explicit ASR transcript textarea/editor and run scoped QA.
- [x] Continue Stage 6 with OCR responsive layout.
- [x] Run final Stage 6 cleanup/theme pass before moving to Stage 5 Settings/plugin cards.
- [x] Complete Stage 5 Settings/plugin cards and run scoped QA.
- [x] Replace crooked Settings icon with centered sliders/controls icon.
- [ ] Run final viewport QA and cleanup.
- [ ] Delete `documentation/progress/mobile-ui-progress.md` after completion.

## Handoff Summary — 2026-05-23
- [x] Current status: Stage 1, Stage 2, Stage 3, Stage 4, Stage 5, and Stage 6 are implemented and locally checked.
- [x] Current active stage completed: Stage 5 Settings Mobile UI.
- [~] Current active stage: Stage 7 QA + cleanup; Settings icon cleanup is complete, final QA/cleanup remains.
- [x] Important changed files: `web_ui/css/style.css`, `web_ui/js/app.js`, `backend/apps/plugins/registry.py`, `backend/apps/plugins/routes.py`, `tests/test_plugin_registry.py`, `documentation/progress/mobile-ui-progress.md`.
- [x] Testing performed: `node --check web_ui/js/app.js`, `venv/bin/python -m py_compile backend/apps/plugins/registry.py backend/apps/plugins/routes.py tests/test_plugin_registry.py`, `venv/bin/python -m unittest tests.test_plugin_registry -q`, static grep for legacy mobile patterns, earlier direct file/static UI geometry checks, Stage 6 local-server Chrome checks, Stage 5 local-server Chrome checks, plugin-doc focused local-server Chrome checks, and Stage 7 Settings icon geometry checks against `http://127.0.0.1:8000/ui/gui_html.html`; no model servers were started by this task.
- [ ] Known external checks still required: real iOS Safari, real Android Chrome, and slow Tailscale connection behavior.
- [x] Documentation decision: `documentation/progress/mobile-ui-progress.md` is temporary task tracking only. Do not migrate progress/history into permanent docs; permanent docs should contain only durable product/technical documentation. Delete this progress file after Stage 7 is fully complete.
- [ ] Current constraints to preserve: no new UI framework, no separate mobile page, no visible native select, no inline styles, no random z-index values, no `overflow-x hidden` as a layout fix.

## Continuation Notes — 2026-05-23
- [x] Done in the latest work block: Stage 5 Settings mobile adaptation, plugin cards responsiveness, plugin docs access, Stage 6 ASR/TTS/OCR cleanup, composer `+` menu opacity fix, and Stage 7 Settings icon visual fix.
- [x] Settings icon final decision: use the controls/sliders metaphor from the provided visual brief, with three continuous lines, hollow knobs, `22px` SVG size, and `1.6px` Settings-only stroke. Keep this shape on every screen size.
- [x] Plugin docs decision: docs pills in Settings are clickable only when the doc is listed in `plugin.json` and exists; backend serves markdown as text and rejects unlisted, missing, unsafe, or non-UTF-8 docs.
- [ ] Not done yet: broad Stage 7 final automated viewport/theme QA, desktop regression pass, final static cleanup of legacy responsive CSS/JS where safe, real iOS Safari check, real Android Chrome check, slow Tailscale behavior check, and final deletion of this temporary progress file.
- [ ] Known remaining issues: ASR Studio mobile is still content-heavy and long-scroll by design; real-device browser behavior has not been validated; slow Tailscale behavior has not been validated.
- [ ] Start next session here: first read this file, confirm the current git state, run a small sanity check against the local UI server if it is running, then continue Stage 7 with the broad viewport/theme QA pass. Do not start permanent documentation migration; this progress file should be deleted only after Stage 7 is fully complete.
