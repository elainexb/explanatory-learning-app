# Explanatory Learning App — Architecture

## Runtime

One Python process serves a loopback-only HTTP interface and owns a SQLite database. The browser uses HTML, CSS, and plain JavaScript. Cytoscape.js 3.34.3 is bundled for graph layout and standard gestures. There is no build server, external frontend CDN, paid API client, or second database.

The application is for one person's local machine. It is not designed for public hosting or multi-user authentication. Requests are checked for local Host/Origin and mutation tokens. Static assets are allowlisted; private runtime files are not a general static directory.

## Responsibilities

| File | Responsibility |
| --- | --- |
| `server.py` | Local HTTP routes, request checks, exact static assets, reference viewing, startup/shutdown |
| `store.py` | SQLite initialization and transactional state changes |
| `core.py` | Cards, topics, shared references, manual candidates, version checks and adoption |
| `generation.py` | One AI task slot, outline/body stages, batching, checkpoints, results and adoption |
| `conversation.py` | Topic messages, questions/options, choices, plans, pending requirements and context |
| `generation_recovery.py` | Read-only explanations and bounded display of unvalidated results |
| `selection_edits.py` | Pinned source selections, discussion/plan/replacement stages, bounded patches |
| `learning_graph.py` | Knowledge relationships, independent reading routes, graph sessions, diff and adoption |
| `references.py` | Local reference originals, snapshots, image validation and reading reports |
| `topic_context.py` | Saved topic preferences and unsummarized user requirements |
| `preferences.py` | Explicitly confirmed shared preference notes and read-back verification |
| `codex_bridge.py` | Installed Codex stdio protocol, subscription checks, schemas, progress and cancellation |
| `index.html` | Main interface, escaped rich reading, card/topic/generation and selection interactions |
| `learning-graph.js`, `learning-graph.css` | Graph UI adapter, accessible list, discussion, manual adjustment and preview |
| `seed.json` | Empty state for first startup only |

Application graph rules live in Python; Cytoscape owns geometry rather than the meaning or correctness of a relationship. A visual position is not evidence of a knowledge prerequisite. Module labels and relationship names are free-form.

## Persistence and adoption

The SQLite `state` row holds one JSON document. User operations run inside transactions. Existing databases are retained on restart. Cards have stable IDs; topics and routes reference them instead of duplicating bodies. Candidate/history data is distinct from adopted content.

Topic body generation checkpoints each validated batch. A failed batch is not counted as complete. All required batches must finish validation before unified adoption. Failed/interrupted work needs explicit continuation.

Selection edits pin a source version, UTF-16 selection offsets mapped to Unicode codepoints, exact text, and shared impact. Only the selected range is replaced on adoption. Graph sessions pin graph/card/topic versions and user-message sequence. New messages or changed versions invalidate stale adoption. Geometry is stored independently for library, topic, and route views.

## AI boundaries

Read/compare, clarify, propose, generate candidate, and adopt are separate steps. A model reply cannot directly update formal content. Confirmation starts generation; adoption is a later explicit operation. Messages submitted during an active task are retained and require a choice to wait/stop/continue rather than silently rerunning.

The bridge uses the default available Codex model with schema-constrained output, ephemeral threads, read-only sandbox, no approval of external side effects, and memory generation disabled. Relevant local memory may be read. App-configured plugin/MCP integrations are disabled in the child connection. Check the actual runtime behavior after upgrades; these flags are not a general security proof.

## Current bounds

- Local Python standard library; Python 3.11+ is required by `tomllib`.
- Outline validation: at most 60 items. Topic generation/discussion includes bounded library summaries, not guaranteed complete understanding of every card body.
- Reference storage: at most 30 references per topic. A generation snapshot uses at most four images, 5 MB per image, and 40,000 reference text characters.
- Body generation: at most three cards per batch; the bridge waits up to 240 seconds for a turn.
- Graph AI input uses full scoped card bodies and rejects over 160,000 input characters rather than silently truncating. Graph routes allow 1–200 steps, including repeated cards for revision.
- Selection length: at most 12,000 characters. Unsupported formatting boundaries require reselection or explicit range expansion.
- No automatic scheduled refresh, video importer, image generator, desktop installer, public deployment support, HTML exporter, or rollback UI.

## Maintenance

Keep storage, content rules, UI, and Codex protocol responsibilities separate. When adding a field or changing a response schema, update validation, candidate preview, adoption checks, and recovery behavior together. Check empty-state startup, real persistence/reopen, conflicts, cancellation, invalid output, and normal/boundary/negative paths outside the release package. This repository intentionally excludes development tests and evidence artifacts at the owner's request; it does not provide a bundled automated suite.

The dependency version and MIT notice are pinned locally. Recheck layout, selection, position round-trips, accessible fallback, CSP, and license attribution when upgrading it. Do not replace explicit adoption with automatic persistence or copy user data into the seed.
