# Project Change Index

## 2026-07-27 — Chat scroll-to-latest button
- Scope: chat history scrolling and streaming response navigation.
- Result: added a persistent latest-message button, preserved streaming auto-scroll behavior, and kept the button visible outside the scroll container while browsing history.
- Key files: `web_ui/gui_html.html`, `web_ui/js/app.js`, `web_ui/css/style.css`
- Verification: manual UI verification, `node --check web_ui/js/app.js`, `git diff --check`, commit `574f40f`

## 2026-07-27 — Mobile UI completion
- Scope: responsive mobile layout, chat composer, settings, ASR/TTS/OCR tools, and viewport QA.
- Result: Mobile UI work was completed and user-verified across the implemented responsive flows; the remaining progress record is closed.
- Key files: `web_ui/gui_html.html`, `web_ui/css/style.css`, `web_ui/js/app.js`
- Verification: user-confirmed QA and previously recorded viewport/theme checks.
