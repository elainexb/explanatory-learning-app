# Explanatory Learning App — Local Data and AI Boundaries

## What the repository contains

Application code, English product documentation, an empty initial state, and the bundled graph dependency/license only. It does not contain personal learning content, references, images, memory notes, credentials, database files, model outputs, development tests, or review logs.

## What running the application creates

| Location | Content |
| --- | --- |
| `data/poc-library.sqlite3` | Your cards/topics, reference metadata/text, discussions, candidates, history and routes |
| `data/reference-images/` | Uploaded image originals |
| `data/codex-runs/` | Per-request prompts, results and diagnostics, which can contain reference text and relevant memory excerpts |
| `~/.codex/memories/extensions/ad_hoc/notes/` | New preferences only after exact-text review and explicit confirmation |

`--db` changes the database path; associated images/logs are placed beside it. `--preferences-dir` overrides the app's confirmed-note directory. It does not isolate or disable the installed Codex runtime's own enabled memory/configuration.

No application state is encrypted at rest. Use your operating system's disk protection and keep backups private. Git ignores local output, but review staged files before every commit. Do not commit an existing database as a demonstration fixture.

## When data reaches AI

Manual viewing, composition, editing, and adoption of existing candidates do not call the model. Explicitly sending/continuing a discussion, requesting a summary/outline, or confirming generation calls the installed Codex runtime and its configured first-party service through the existing ChatGPT login. Relevant cards, requests, enabled references/images, and relevant memory/preferences may be part of that input.

Local-first means local application storage; it does not mean offline AI or that prompts stay on the computer. URLs may be fetched during an authorized AI request. Uploading or saving a local reference alone does not prove it has been read.

The app does not ship a user's Codex memory. At runtime, shared memory supplies relevant background; it is not automatically copied from an entire chat. New topic preferences stay with that topic unless the separate remember-and-confirm workflow is used.

## Access and fees

The server binds to `127.0.0.1` only. Do not expose it through a public tunnel or bind it to all interfaces. The application has no multi-user permission system and should not be deployed publicly.

The bridge does not require API keys, uses a ChatGPT Plus login check, rejects extra-credit/unknown allowance states, and has no paid fallback. It still consumes shared subscription allowance. Checks depend on the installed Codex protocol and account state; they are not an unlimited-free guarantee or an atomic billing lock across other sessions.

## Before sharing

Review the exact staged list. Keep `data/`, `.env` files, `.codex/`, credentials, exports, personal sources, generated material, and development checks untracked. The release allowlist is an additional guard, not a substitute for reviewing what you share.
