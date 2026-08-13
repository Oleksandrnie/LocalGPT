# Prompt, RAG and LLM Security Audit

## Scope and evidence baseline

This report records the Stage 1 state of `dev` commit `c32a101c876757890bacd4d3c89022e88f97e8e3`. It uses only synthetic fixtures. It does not claim absolute prompt-injection protection and does not contain client corpus text, secret values, raw hidden prompts or live-model outputs.

Evidence sources:

- prompt composition: `app/roles.py`, `app/prompts/system_base.md`, `backend/apps/chat/service.py`, `backend/apps/chat/routes.py`;
- RAG ingestion/retrieval: `backend/apps/rag/service.py`, `backend/apps/rag/routes.py`, relevant database repositories in `app/db.py`;
- derived context: `backend/apps/chat/services/vision_context.py`, `backend/apps/chat/tasks.py`, `backend/apps/asr/pipeline.py`;
- storage, ownership and lifecycle: profile/session routes, chat attachments/tasks, RAG context export and reasoning routes;
- sinks and actions: model/runtime, OCR/ASR/TTS, plugins, model transfer, operational routes and UI Markdown rendering;
- reproducible baseline: `tests/test_prompt_rag_security_audit.py`, `tests/fixtures/prompt_rag_security/` and `tests/markdown_rendering.test.mjs`.

## Prompt and data-flow map

The current text-chat order is exact for `build_messages`; optional blocks are omitted when empty.

| Order | Block | Owner | Trust | Current role | Size control | Current boundary and diagnostics |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | base prompt + language suffix | backend | L1 | `system` | file/fallback not explicitly capped | loaded by `app.roles.system_prompt_for`; raw value returned by debug prompt endpoint |
| 2 | profile system prompt | active profile | L2 | `system` | no schema maximum | free text prefixed with a label; raw value returned by debug endpoint |
| 3 | request profile/user context | request caller | L4 | `user` | no schema maximum | label only, no structured envelope |
| 4 | summary memory | profile/session DB, model-derived | L4 | `user` | item count setting; no per-item builder cap | source type label; model summary may contain instruction-shaped text |
| 5 | RAG context | active profile sources/chunks | L4 | `system` | `rag_top_k` and `rag_max_context_chars`, both caller-configurable within broad settings | incorrectly promoted to instruction-bearing `system`; source/role/score label, no trust envelope |
| 6 | processed/raw transcript | active session/request | L4 | `user` | processed transcript cap; raw request transcript has no schema cap | label only |
| 7 | criteria | request/session or explicit Google Sheet import | L2/L4 configuration data | `user` | count 200; no per-item schema cap | label only; content can be instruction-shaped |
| 8 | response-language/format hint | backend | L1 | `system` | backend constant | appended after data blocks, but does not define full security hierarchy |
| 9 | short history | active session DB | L4/L5 | original `user`/`assistant` roles | turn count only | assistant claims remain indistinguishable from evidence to the model |
| 10 | current query | request caller | L3 | `user` | no schema maximum | final task instruction |

Additional flows:

- Auto routing sends the current query and bounded metadata to a dedicated local router model. Its output is schema-normalized and mapped to backend-owned model IDs; it cannot invent a target model or select the calculator automatically.
- OCR text and vision-derived context are appended as `user` data with explanatory labels. They are not yet placed in the same structured L4 envelope as other derived sources.
- The Mistral code hint rewrites only the final user message with a backend-owned prefix.
- ASR pipeline stages use separate backend-owned prompts plus transcript/profile analysis configuration. They do not feed arbitrary actions into the chat runtime, but transcript and analysis prompt size/boundary checks remain part of runtime hardening.
- No universal external-agent/MCP/webhook ingress or agent-to-agent execution channel exists on the base commit. Criteria can explicitly fetch a Google Sheet from a fixed Google domain; plugins expose only backend-owned handlers.

## Asset, confidentiality, ownership and retention inventory

| Asset | Confidentiality | Owner/scope | Persistence/retention | Current exposure |
| --- | --- | --- | --- | --- |
| global prompt | hidden policy/runtime data | backend | tracked runtime file | debug prompt endpoint returns raw content |
| profile prompt/preferences | private profile configuration | profile | SQLite until profile deletion | profile APIs and debug prompt; no authenticated principal beyond local profile selection |
| sessions/messages/criteria | private conversation data | profile + session | SQLite until deletion/reset | session APIs use object IDs; several routes lack an explicit profile ownership argument |
| assistant reasoning | highly sensitive derived data | profile + session + message | capped SQLite field | dedicated route verifies profile/session ownership; not returned in normal history |
| summary memory | private model-derived data | profile + session | SQLite until cleanup | included in prompts and debug output |
| manual RAG files/chunks | private local sources | profile | filesystem + SQLite until deletion | profile-scoped retrieval; status/debug expose paths or source metadata |
| ASR/vision/chat-derived RAG | private derived sources | profile + session/message | SQLite, source-specific deletion | export checks session/message ownership; assistant exports remain derived, not independent truth |
| attachments | private binary data | profile + optional session/message/task | local storage until cleanup/profile/session deletion | media/delete verify profile; worker paths remain internal |
| chat task artifacts | private transient output/reasoning | profile + session + random task id | JSON/JSONL until task cleanup | task/status/events/cancel use task id without explicit profile check |
| chat/pipeline/transcribe logs | private diagnostic data | runtime | local files, rotation/retention varies | chat currently records raw query/reply/error; errors may contain paths/provider text |
| model/runtime settings | internal configuration | profile/runtime | SQLite/environment | health/version/debug return more internal metadata than normal UX needs |
| secrets and tokens | secret | process/runtime | environment | no intentional prompt inclusion; raw exception/log paths can accidentally capture values |

The application is a local multi-profile runtime, not a multi-user identity service. Profile IDs are therefore the existing isolation boundary. This audit treats cross-profile access as unauthorized even when a caller can reach the local/LAN API.

## Entry points and sinks

### Untrusted text entry points

- `/chat`, `/chat/tasks`: query, context, transcript, criteria and selected object IDs.
- profile create/update/preferences: profile prompt and ASR analysis prompt.
- session criteria and `/criteria/parse`: text/CSV/XLSX or explicit fixed-domain Google Sheet import.
- RAG upload and explicit chat/vision/ASR export: Markdown and derived text.
- image upload/OCR/vision: binary plus OCR/vision-derived text.
- chat history, summary memory and stored assistant output.
- plugin documentation is displayed as plain text/Markdown data; manifests are parsed as data and cannot add handlers.

### Model-output sinks and action inventory

| Sink/action | Model-output data flow | Current control/evidence |
| --- | --- | --- |
| chat response/history/SSE | yes, text and separately stored reasoning | text is stored/streamed; final content is sanitized for formatting but not treated as authority |
| browser rendering | yes | `web_ui/js/markdown.mjs` HTML-escapes raw text and code; synthetic XSS tests cover tags/event attributes/script-shaped content |
| SQLite | yes, as values only | repository methods use fixed SQL with parameters; no model-generated SQL execution path found |
| shell/subprocess | no implicit flow found | subprocess argument lists are constructed by backend model/ASR/OCR/TTS/network handlers; no chat-output-to-command edge found |
| local calculator | no output flow | parses the current user request with a constrained AST evaluator; auto-router output cannot select it |
| filesystem paths | no implicit output flow found | backend-owned paths, resolved roots and allowlisted suffixes are used; chat output is not a path input |
| URLs/network | no implicit output flow found | Ollama/model catalogs/downloads and criteria Google export use backend/config/user-owned targets; chat output is not forwarded |
| plugins | no model-output flow found | manifests are data; only the hard-coded `tailscale` handler can be effective |
| runtime shutdown/restart/database reset | no model-output flow found, but API action exists | direct API caller can invoke operational endpoints with insufficient authorization |
| external agent/webhook | absent | no generic connector or action channel exists on the base commit |

Absence of an implicit data-flow edge is evidence about the base commit, not a permanent guarantee for future connectors.

## Grounding baseline

The synthetic query is: “С какими CMS вы работаете и как продвигаете сайты по регионам России?” The corpus contains separate CMS and regional service evidence, a repeated aggregate/CTA page, current and stale conflicting statements, and an instruction-shaped poisoned document.

Current `local-hash-v1`, `top_k=5` result order:

1. `duplicate-aggregate.md`, chunk 0, score `0.4016`;
2. `duplicate-aggregate.md`, chunk 1, score `0.3852`;
3. `regions.md`, chunk 0, score `0.3021`;
4. `conflict-current.md`, chunk 0, score `0.2536`;
5. `cms.md`, chunk 0, score `0.2302`.

Observed metrics and limits:

- both query facets are present at `top_k=5`, but one duplicate source consumes 40% of the retrieval budget and ranks above both specific sources;
- `build_context` stops at the first block that exceeds the remaining character budget, so an oversized/repeated early source can prevent later small, high-value blocks from being considered;
- no minimum score, facet coverage, contradiction, stale-source, source-diversity or near-duplicate gate exists;
- source and chunk IDs are available in retrieval results, but context carries only source/role/score and no claim-level `supported`/`not_found`/`inference` state;
- `truth_priority`, derived `message_role` and source freshness metadata are not consistently used by ranking; explicitly exported assistant text can therefore re-enter retrieval without independent-source confirmation;
- the hash vector is deterministic and offline but is lexical hashing, not semantic meaning; the prefix matcher is language-specific and can miss paraphrases.

Stage 3 must compare, on this same harness and additional exact-fact cases:

1. normalized lexical/BM25 or SQLite FTS retrieval with deduplication and source diversity;
2. a fully local semantic embedding candidate only if its model files, license, latency, memory, offline availability and reproducibility meet the project constraints.

The selection metric is facet coverage and supported-claim recall first, then duplicate rate, conflict visibility, exact-fact regression, p95 latency and memory. A semantic dependency is not approved merely by being more sophisticated.

## Corpus hygiene baseline

Current ingestion enforces Markdown-only files, a 5 MiB per-file read limit, profile-scoped directories and deterministic chunks. It does not report duplicate/near-duplicate ratio, boilerplate ratio, oversized page/chunk distribution, missing headings, stale/conflicting facts or suspicious instruction-like text. It also reads an entire uploaded file before applying the size comparison. Any future cleanup must be preview-only until the user confirms source changes; this task will not silently delete corpus files.

## Threat register

Severity follows the task specification. No confirmed Critical finding exists on the base commit because no unauthenticated model-output-to-code/secret/cross-profile compromise was demonstrated.

| ID | Scenario and preconditions | Impact/likelihood | Current controls and evidence | Severity |
| --- | --- | --- | --- | --- |
| PRS-01 | instruction inside RAG is inserted as `system` | reliable indirect policy influence; likely with poisoned/high-score content | grounding prose only; synthetic expected failure | High |
| PRS-02 | global prompt lacks explicit hierarchy, hidden-prompt privacy and non-executable-output policy | direct/profile/history injection can reliably contest policy; medium likelihood | language/format and basic no-fabrication text only | High |
| PRS-03 | assistant history or explicit assistant-to-RAG export is reused as evidence | self-citation and unsupported facts; likely | source metadata exists but ranking/prompt policy does not exclude it | Medium |
| PRS-04 | no claim-level provenance/status/coverage/conflict contract | incomplete multi-part answers and silent conflicts; likely | source/chunk IDs exist in search results | Medium |
| PRS-05 | duplicates and oversized early chunks consume retrieval/context budget | one source displaces complementary evidence; demonstrated | top-k and char cap only | Medium |
| PRS-06 | raw query, reply and exception strings are written to chat log | local private data/secret/path leakage; reliable when chat logs are readable | local file only; no redaction | Medium |
| PRS-07 | local/dev debug prompt endpoint returns raw messages/profile prompt without token | hidden prompt/private context disclosure to any reachable local/LAN caller; reliable | production mode can require token; local/dev bypasses it | High |
| PRS-08 | chat/RAG schemas lack per-block input and top-k bounds; no total prompt budget | memory/CPU amplification and context overflow; easy | generation token caps and some transcript/RAG settings exist | Medium |
| PRS-09 | task/status/events/cancel endpoints use only random task ID | cross-profile task membership/output/cancel if ID is learned; bounded | high-entropy IDs; reasoning and attachments have stronger ownership checks | Medium |
| PRS-10 | shutdown/restart/database maintenance endpoints lack consistent authorization | destructive/high-impact local/LAN action; reliable for a reachable caller | database reset requires a public confirmation literal, not authority | High |
| PRS-11 | health/version/RAG status expose internal filesystem and network/runtime metadata | bounded reconnaissance/privacy leak; likely | local deployment assumption | Medium |
| PRS-12 | RAG upload count/total bytes and pre-read allocation are unbounded | request memory/disk pressure; likely under abuse | per-file 5 MiB check after read, suffix allowlist | Medium |
| PRS-13 | prompt/profile/history/suspicious-content diagnostics do not share a safe metadata-only contract | difficult detection and unsafe raw debug temptation | `prompt_blocks` omits values but debug also returns full messages | Low |
| PRS-14 | global base prompt mixes persona/style with policy | profile behavior migration risk and policy ambiguity | editable profile prompt already exists | Medium |
| PRS-15 | model-derived summary/vision/OCR/transcript text uses labels, not uniform L4 envelopes | indirect injection can influence completion; medium likelihood | mostly `user` role and explanatory prose | Medium |
| PRS-16 | errors may return provider exception text and criteria fetch failures verbatim | paths/network details in terminal errors; bounded | some routes map structured codes; inconsistent redaction | Medium |

Confirmed positive controls:

- RAG database search is profile-scoped; chat/vision context export validates profile, session and message relationships.
- attachment media/delete and reasoning retrieval enforce profile ownership; reasoning is absent from normal history and capped in storage.
- UI rich-message rendering escapes HTML and code content.
- plugin manifests cannot register executable code; only hard-coded trusted handlers run.
- local calculator uses a constrained AST and consumes user input, not model output.
- router output is normalized against a backend-owned intent-to-model map.
- no implicit chat-output edge to subprocess, SQL, filesystem, URL, plugin or webhook action was found.

## Remediation matrix

| Finding | Owner/boundary | Planned fix | Required tests | Residual risk after fix |
| --- | --- | --- | --- | --- |
| PRS-01, PRS-15 | chat prompt builder, L1/L4 boundary | uniform structured data envelopes; never place raw RAG/derived data in instruction-bearing system content | direct/indirect injection for RAG, transcript, OCR, vision, memory, criteria and history | models can still misunderstand delimiters; code actions remain separately denied |
| PRS-02, PRS-14 | global prompt + profile configuration | compact immutable guard policy; move default persona to profile-owned default with reversible migration | ordering/snapshot, direct extraction/action injection, persona compatibility/migration | natural-language policy is defense-in-depth, not authority enforcement |
| PRS-03, PRS-04 | prompt builder + grounding diagnostics | mark assistant history/exports as non-evidence; claim evidence statuses and contradiction/partial-coverage behavior | self-citation, missing fact, conflict, inference and partial multi-part cases | final free text may still need model/eval validation |
| PRS-05 | RAG service | evaluated lexical/hybrid retrieval, duplicate/source diversity and facet-aware context packing | CMS + regions, duplicate/stale/conflict and exact-fact golden cases; latency/memory | local semantic recall may remain limited offline |
| PRS-06, PRS-07, PRS-11, PRS-13, PRS-16 | logging/debug/public API | metadata-only structured logs/debug, mandatory admin authorization, path/exception redaction | secret markers absent from logs/responses; local/dev denial without token | local administrator can intentionally inspect data through controlled paths |
| PRS-08, PRS-12 | schemas/request service/RAG upload | per-block, aggregate, top-k, upload count/bytes and context budgets before allocation/work | max-valid and over-limit cases with stable 4xx errors and no artifacts | token estimates remain approximate across models |
| PRS-09 | chat task routes/storage | require and verify profile/session ownership for status/events/cancel; uniform not-found response where appropriate | guessed/foreign task IDs, replay/reconnect and cancel cleanup | possession of the active profile remains the local authority model |
| PRS-10 | operational routes | admin-token/confirmation policy for destructive/high-impact operations, safe local defaults | unauthorized/authorized shutdown/restart/reset/cleanup contract tests | OS-level local users remain outside application auth scope |

## Remediation status

Stage 2 implements the prompt-source boundary portion of the matrix:

- PRS-01 and PRS-15 are structurally mitigated: RAG, request context, memory, transcript, OCR/Vision-derived text, criteria and history are uniform L4 data envelopes and are never promoted to instruction-bearing system content.
- PRS-02 and PRS-14 are structurally mitigated: the global prompt is policy-only, the default behavior/persona is versioned profile configuration, and the one-shot migration preserves every non-empty existing profile prompt byte-for-byte while recording its origin.
- PRS-03 is partially mitigated: assistant history is marked continuity-only and the immutable guard denies self-citation as evidence. Claim-level evidence status and explicit handling of assistant-authored RAG exports remain Stage 3 work.
- PRS-04 remained open after Stage 2 for claim provenance, coverage, conflict, not-found and inference diagnostics; its Stage 3 status is recorded below.

The Stage 2 evidence is deterministic prompt composition, ordering, metadata-only snapshot, forged-boundary escaping, migration and ASR/OCR/Vision source tests. No live model was loaded, so these controls do not establish model-level jailbreak resistance; authorization and actions remain code-enforced boundaries.

Stage 3 implements the retrieval and evidence portion of the matrix:

- PRS-03 is mitigated for retrieval: assistant-authored Chat exports remain stored/editable continuity data but are excluded from factual evidence selection; prior assistant output cannot satisfy a facet.
- PRS-04 is mitigated for internal/test evaluation: query facets carry `supported`, `partial`, `conflict` or `not_found`, with source id, chunk id and a bounded evidence span. These diagnostics are placed inside the L4 RAG envelope; user-facing citation UI remains out of scope.
- PRS-05 is mitigated by the selected offline `hybrid_v1` candidate: BM25-style lexical ranking, facet-first selection, repetition penalties, near-duplicate suppression and source diversity replace score-only top-k. The legacy candidate remains a data-preserving rollback mode.
- Corpus hygiene is preview-only and metadata-only. It identifies duplicate/boilerplate, oversized/missing-heading/stale/potential-conflict and suspicious-instruction sources without deleting or rewriting them.

On the synthetic CMS + regions case, legacy top-2 was the same aggregate source twice; hybrid top-2 was the specific CMS and regions sources. A 100-iteration local observation measured approximately 3.14 ms/query and 1.56 MB peak for legacy versus 10.59 ms/query and 2.16 MB peak for hybrid. A semantic model candidate was not eligible without a new model/dependency and heavy download, so it was not loaded. Residual risks are heuristic stemming/conflict detection, context-budget sensitivity, and model-level use of diagnostics.

## Rollout and rollback

1. Ship prompt boundaries behind deterministic builder contracts, with snapshot metadata that never includes raw secret values.
2. Migrate only the default persona: existing non-empty profile prompts remain byte-for-byte user-owned. New/empty profiles receive the versioned default persona. Store a migration marker and never overwrite user text.
3. Keep the previous prompt builder and retrieval algorithm selectable by a local rollback setting for one release/canary window; rollback changes composition/ranking only, not stored profile prompts or corpus.
4. Run synthetic tests and exact-fact/profile-isolation tests before enabling new retrieval by default. Compare latency/memory offline.
5. Apply API/logging/authorization controls independently from retrieval so rollback cannot re-open Critical/High boundaries.
6. Do not mutate or delete user RAG files during rollout. Corpus hygiene output is diagnostic/preview only.

## Residual risks and untested environments

- Live-model resistance varies by model and quantization; Stage 1 did not load any model. At least one thinking and one non-thinking model require a bounded Stage 5 comparison.
- Real corpus duplication, stale content and multilingual paraphrase distribution were not inspected because client data must not enter the audit artifacts.
- LAN/tailnet reachability, reverse-proxy headers, OS file permissions and log access were not exercised in this environment.
- Browser desktop/mobile/theme/accessibility checks remain pending until a user-visible UI change exists.
- No external-agent channel exists to test. Future connectors must add authenticated principals, capability scopes, schema validation, replay/idempotency protection, confirmation and loop budgets before accepting messages.
- Prompt/data envelopes reduce ambiguity but cannot guarantee model obedience. Authorization, limits, ownership and safe sinks must remain code-enforced.
