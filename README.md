# Leaflet — Local Card Learning

A local-first proof of concept for building reusable knowledge cards, combining them into saved topics, and exploring relationships through a knowledge graph and personal reading routes.

The repository starts empty. It contains application functionality only: no study handbook, job descriptions, uploaded images, personal cards, memory contents, databases, generation logs, or test files.

## Run locally

Requirements:

- Python 3.11 or newer, with SQLite and the standard library. No pip or npm installation is required.
- A modern browser. The graph library is bundled locally.
- For AI features: a compatible installed Codex runtime, network access, and a signed-in ChatGPT Plus account. Manual reading and editing work without an AI call.

On macOS, double-click `Start.command`, or run:

```sh
bash Start.command
```

Alternatively:

```sh
python3 server.py
```

Open `http://127.0.0.1:8767/`. Keep the terminal open; Control+C stops the server. If another copy is already using that port, use:

```sh
bash Start.command --port 8768
```

`--no-browser` suppresses automatic browser opening. `--db /path/to/library.sqlite3` chooses a different local database. The launcher first checks `/usr/local/bin/python3`, then Python on PATH; confirm that the selected interpreter meets the version requirement.

This runtime was developed on an Intel Mac running macOS 14.4.1 with 8 GiB RAM. There is no desktop shell, local model download, build step, or production Node.js dependency. Other operating systems and browser combinations have not been verified.

## Start with your own content

1. Create a topic, write its learning goal and expansion preferences, and save it. Or create a card directly.
2. Use **Discuss and adjust** to ask questions, clarify scope, compare approaches, or propose changes. AI can ask questions with choices and accepts free-text answers.
3. Choose **Generate needed cards** to generate an outline first. AI proposes card count, learning coverage, and existing-card reuse. Review the outline before confirming body generation.
4. Bodies are generated in sequential batches of at most three cards, with saved checkpoints. Stop at any time. After failure or interruption, explicitly continue from unfinished work; failed batches are not retried automatically.
5. Review candidates, source reports, and verification notes. **Adopt** saves new cards and adds them to the topic. Discarding leaves saved content unchanged.

### Saved cards and topics

- Reuse the same card in multiple topics; each topic has its own selection and reading order.
- Edit learning goals and expansion preferences directly. Summaries of additional requirements remain editable drafts until saved.
- Continue from a previous outline/body version or deliberately plan from scratch. History distinguishes latest requests from completed results and adopted content.
- Add text, a job description, a web URL, or PNG/JPG/WebP references. Originals are local, can be renamed/disabled, and are supplied to Codex only when an AI request needs them. Saving a URL does not prove it was read or fact-checked.
- Body rendering supports headings, emphasis, lists, quotes, code, links, and simple tables. Raw HTML is escaped.

### Interactive selection edits

Open a saved card, select a sentence or paragraph, and choose **Discuss selection** or right-click. Discuss or clarify first, confirm a plan, review the localized replacement, then continue adjusting or adopt. The application pins the card version and source range and preserves text outside that range. Shared-topic impact is shown before adoption. Selection editing currently applies to saved cards, not unadopted generation candidates.

### Knowledge graph and reading routes

Open **Knowledge graph** to view all saved cards or a topic. Search, filter modules, and explore adjacent cards. Ask AI to organize relationships and routes for a learning goal; confirm its plan before generating candidates. Read relationship reasons and supporting quotes before adoption.

Relationships and reading routes are separate. A relationship describes a connection; a route chooses what to read and why, in a particular order. Multiple routes reuse the same cards. You can edit modules, custom relationship labels, route steps, reasons, and node positions manually. Changes are previewed before adoption. Updating shared relationships shows affected routes but does not silently reorder them. Graph operations do not rewrite card bodies or the topic's original order.

## AI connection and shared preferences

The application calls the installed Codex `app-server` over local stdio. It does not require an API key, use a paid API fallback, or install another agent service. The adapter currently requires a confirmed ChatGPT Plus login, readable allowance windows, and zero extra credits. Unknown status, exhausted allowance, or extra credits block generation.

AI requests consume the account's shared subscription allowance. Included allowance is not unlimited, and the local check is not an atomic billing guarantee if account settings change elsewhere. There is no automatic fallback or failed-call retry.

Codex may use relevant enabled local memory for background and preferences; this is not a copy of an entire chat. New global preferences require **Remember a learning preference**, review of the exact wording, and explicit confirmation. The app writes a separate note rather than editing generated memory files. See [PRIVACY.md](PRIVACY.md) for locations and transmission boundaries.

The Codex protocol and model availability can change. This is an experimental, personal local application rather than a supported public integration. Recheck authentication, usage handling, structured output, cancellation, image input, and memory behavior after a runtime upgrade.

## Persistence and recovery

Runtime data is created under `data/` and excluded from Git. Refreshing/restarting does not reimport the empty seed over an existing database. To back up, stop the program and copy `data/`. Copying the repository alone does not copy your library.

Messages, questions, choices, plans, candidate versions, and adoption records are saved. Failed tasks retain requirements and earlier checkpoints and give recovery actions. Pending messages and stale card/topic/graph versions prevent adopting an older result over newer work. History supports traceability; there is no one-click rollback interface.

Only submitted information is persisted. Unsent input stays in the page, with leave warnings where supported. Candidate validity, matching quotations, and successful saves do not prove factual accuracy or learning effectiveness. Review content before adopting it.

## Repository boundaries

The root `.gitignore` uses an explicit release allowlist. Add new functional files deliberately after reviewing them. Keep generated content, credentials, local memory, personal references, development checks, and runtime output outside commits. The bundled empty `seed.json` is application initialization, not sample learning content.

Implementation boundaries and limits: [ARCHITECTURE.md](ARCHITECTURE.md). Bundled dependency attribution: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

This copy is English-first: interface text, interaction prompts, diagnostics, and documentation are English. User-authored content may use other languages; selected-text replacement follows the user's requested language. No account or study data is included.
