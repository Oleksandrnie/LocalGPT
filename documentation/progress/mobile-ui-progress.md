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
- [ ] Status: pending.
- [ ] Scope: full-screen modal or bottom-sheet behavior, responsive tabs/sections, mobile-friendly forms, checkbox cards, plugin cards, model settings, internal scroll behavior.
- [ ] Related files: `web_ui/css/style.css`, `web_ui/js/app.js`, `web_ui/gui_html.html`, `documentation/progress/mobile-ui-progress.md`.
- [ ] Local QA: settings viewport checks, dark/light checks, desktop regression check.

## Stage 6 — ASR/TTS/OCR Mobile
- [~] Status: in progress; TTS Voice Studio, ASR transcript editor, ASR/TTS opacity cleanup, and OCR mobile layout completed; final Stage 6 cleanup remains.
- [ ] Scope: ASR Studio and TTS Voice Studio single-column layout, full-width controls, `AppSelect` preservation, history/cards without horizontal overflow, touch-friendly action buttons, OCR editor mobile behavior.
- [ ] Related files: `web_ui/css/style.css`, `web_ui/js/app.js`, `web_ui/gui_html.html`, `documentation/progress/mobile-ui-progress.md`.
- [x] Local QA: TTS Voice Studio Chrome CDP viewport metrics for 375x667, 390x844, 412x915, 430x932, 667x375 landscape, and 1440x900 desktop.
- [x] Current sub-scope: fixed TTS Voice Studio mobile overlap only; ASR/OCR remain pending within Stage 6.
- [x] Current sub-scope: added explicit ASR transcript textarea/editor and kept export/chat/context actions on the same `#asrToolOutput` source.
- [x] Local QA: ASR Studio headless Chrome file-based geometry checks for 375x667, 390x844, 412x915, 430x932, 667x375 landscape, and 1440x900 desktop; no backend/model server started.
- [x] Current sub-scope: reduced ASR/TTS tool window transparency so the main page does not bleed through while reading.
- [x] Local QA: computed ASR/TTS tool window backgrounds are opaque `rgb(...)` in dark and light themes; no backend/model server started.
- [x] Current sub-scope: adapted OCR attach/editor mobile layout, removed overlap/overflow, preserved attach flow and editor actions.
- [x] Local QA: OCR editor headless Chrome file-based geometry checks for 375x667, 390x844, 412x915, 430x932, 667x375 landscape, reduced-height 375x420 keyboard simulation, and 1440x900 desktop; no backend/model server started.
- [ ] Remaining Local QA: full Stage 6 tool window cleanup, dark/light pass, desktop regression check.

## Stage 7 — QA + Cleanup
- [ ] Status: pending.
- [ ] Scope: landscape testing, iOS Safari fixes, Android Chrome fixes, slow Tailscale behavior notes, cleanup legacy responsive CSS/JS, permanent documentation updates, temporary progress file deletion.
- [ ] Related files: `README.md`, `TECHNICAL_README.md`, `docs/ui-components.md`, `documentation/ui-components.md`, `web_ui/css/style.css`, `web_ui/js/app.js`.
- [ ] Local QA: automated browser viewport pass where available, desktop regression pass, final static grep for deprecated responsive patterns.

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

## In Progress
- [~] Stage 6 final ASR/TTS/OCR cleanup and theme pass.

## Pending
- [ ] Stage 5: Settings mobile full-screen/bottom-sheet behavior and form/card overflow fixes.
- [ ] Stage 6 remaining: final ASR/TTS/OCR cleanup and dark/light pass.
- [ ] Stage 7: dark/light theme pass, viewport QA, documentation updates, cleanup, and progress file deletion.

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
- ASR Studio reuses the existing `#asrToolOutput` textarea as the single source for save/download/copy/prompt/chat actions; no duplicate mobile transcript component was added.
- ASR Studio mobile uses flex-based vertical flow inside `.tool-window__body` so tab content contributes real height and cannot overlap action/history sections.
- ASR/TTS tool windows now use semantic `--tool-window-bg` and `--tool-window-header-bg` tokens instead of translucent page-bleed backgrounds.
- OCR editor reuses the existing `#ocrTextOutput` textarea as the single source for insert/send/clear actions; scoped `#ocrBackdrop` mobile rules avoid changing Stage 5 Settings.
- OCR modal uses safe-area insets, body scroll lock, and a reduced-height path for landscape/software-keyboard behavior.

## Changed Files
- `documentation/progress/mobile-ui-progress.md`
- `web_ui/css/style.css`
- `web_ui/js/app.js`
- `web_ui/gui_html.html`

## Known Issues / Technical Debt
- [ ] ASR floating window still carries legacy fullscreen `!important` rules and desktop-oriented dimensions; this will be cleaned later in Stage 6.
- [ ] ASR Studio mobile remains content-heavy and long-scroll by design for now; later Stage 6 cleanup can compact secondary action groups if needed.
- [ ] Settings mobile modal still uses older bottom-sheet/fullscreen rules; this will be normalized in Stage 5.
- [ ] Plugin cards/actions inside Settings are not mobile-adapted yet; include them in Stage 5 Settings Mobile UI.
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
- [ ] Dark theme mobile pass
- [ ] Light theme mobile pass
- [x] Desktop visual regression pass for topbar/composer metrics
- [ ] Real iOS Safari device check
- [ ] Real Android Chrome device check
- [ ] Slow Tailscale connection behavior check

## Next Steps
- [x] Fix TTS Voice Studio mobile overlap and run viewport QA.
- [x] Add explicit ASR transcript textarea/editor and run scoped QA.
- [x] Continue Stage 6 with OCR responsive layout.
- [ ] Run final Stage 6 cleanup/theme pass before moving to Stage 5 Settings/plugin cards.
- [ ] Run viewport QA and update permanent docs.
- [ ] Delete `documentation/progress/mobile-ui-progress.md` after completion.

## Handoff Summary — 2026-05-23
- [x] Current status: Stage 1, Stage 2, Stage 3, Stage 4, and Stage 6 sub-tasks for TTS, ASR editor, ASR/TTS opacity, and OCR editor are implemented and locally checked.
- [~] Current active stage: Stage 6 final ASR/TTS/OCR cleanup and theme pass.
- [ ] Next implementation stage after Stage 6 cleanup: Stage 5 Settings Mobile UI, including plugin card/action responsiveness.
- [ ] Final stage after Settings: Stage 7 QA + cleanup + documentation updates + deletion of this temporary progress file.
- [x] Important changed files: `web_ui/css/style.css`, `web_ui/js/app.js`, `web_ui/gui_html.html`, `documentation/progress/mobile-ui-progress.md`.
- [x] Testing performed without starting backend/model servers: `node --check web_ui/js/app.js`, static grep for legacy mobile patterns, headless Chrome geometry checks using direct file/static UI.
- [ ] Known external checks still required: real iOS Safari, real Android Chrome, and slow Tailscale connection behavior.
- [ ] Current constraints to preserve: no new UI framework, no separate mobile page, no visible native select, no inline styles, no random z-index values, no `overflow-x hidden` as a layout fix.
