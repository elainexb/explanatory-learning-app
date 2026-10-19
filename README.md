# Explanatory Learning App (POC)

Turn a learning goal into small, reusable cards with explanations, concrete examples, and sources. Combine the cards into topics, discuss changes with AI, and explore their relationships through a knowledge graph and personal reading routes.

**Status: proof of concept for personal, local use.** The project starts with an empty library. It includes application functionality only, with no personal learning material, references, memory contents, databases, generation logs, or tests.

The application is one Python process plus a browser interface. There is no frontend build, pip dependency installation, npm installation, Docker requirement, or local model download. Codex is a separate prerequisite for AI features; manual card/topic features work without a model call.

- [Prerequisites](#prerequisites)
- [Set up and launch](#set-up-and-launch)
- [First learning session](#start-with-your-own-content)
- [AI connection and shared preferences](#ai-connection-and-shared-preferences)
- [Persistence and recovery](#persistence-and-recovery)
- [Troubleshooting](#troubleshooting)

## Prerequisites

| Requirement | Needed for | How to check or obtain it |
| --- | --- | --- |
| Python 3.11 or newer, including SQLite, `tomllib`, and timezone data | All features | Run the Python checks below. Install Python from [python.org](https://www.python.org/downloads/) if needed. Some system-provided Python versions are too old. |
| A modern browser | All features | Open the local HTTP URL printed at startup. Do not open `index.html` as a file. |
| A writable project/data directory | Saving | Extract the project into a normal folder you can write to. Do not run it inside the ZIP archive or a read-only location. |
| Installed Codex with a compatible `app-server` protocol | AI features | Install using the [official Codex CLI guide](https://learn.chatgpt.com/docs/codex/cli); confirm `codex --version` and `codex app-server --help` work. The desktop main window does not need to stay open. |
| Your own ChatGPT Plus login and available subscription allowance | AI features | Run `codex login`, then `codex login status`. **This POC specifically accepts Plus, not every plan supported by Codex.** The app also requires readable allowance information and zero extra credits. |
| Network access to the Codex service | AI features | AI generation is online. Local storage does not mean offline inference. |

Git is optional for running a downloaded project folder. Node.js is not required by the application or by the standalone Codex installation method below.

**Platform scope:** local startup and core workflows have been checked on an Intel Mac running macOS 14.4.1, Python 3.14.7, and SQLite 3.53.4. These are a reference environment, not required exact versions or a minimum hardware specification. Apple Silicon, Linux, and native Windows have not been verified as complete installations. `Start.command` is a macOS launcher; this POC is not a cross-platform one-click installer. Check the target computer's Python, SQLite/timezone support, Codex runtime, permissions, and network before relying on it.

## Set up and launch

### 1. Get the application folder

Download and extract the project ZIP, or obtain a Git checkout. This document does not assume a particular GitHub owner or repository URL. Open Terminal and enter the folder containing `server.py`, `seed.json`, and `Start.command`:

```sh
cd explanatory-learning-app
```

If an extracted folder has a suffix such as `-main`, use its actual name. On macOS, you can type `cd ` and drag the extracted folder into Terminal to insert its path, then press Enter.

### 2. Check Python

```sh
python3 --version
python3 -c "import sys, sqlite3, tomllib; from zoneinfo import ZoneInfo; assert sys.version_info >= (3, 11), 'Python 3.11+ required'; ZoneInfo('Asia/Shanghai'); print('Python and SQLite ready:', sqlite3.sqlite_version)"
```

The first command must show Python 3.11 or newer. The second should print `Python and SQLite ready:` and a SQLite version. It only checks local prerequisites; it does not contact AI or read your learning library. If it fails, see [Troubleshooting](#troubleshooting).

### 3. Install and sign in to Codex — AI features only

Skip this step to try manual cards, topics, and manual graph editing first.

If `codex` is not installed, the official standalone installer for macOS/Linux is:

```sh
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

This downloads and runs the official installer; use the [official installation guide](https://learn.chatgpt.com/docs/codex/cli) to review installation choices. Restart Terminal if needed so the installed command is on PATH. This project does not install Codex automatically.

Then check the runtime and sign in with **your own ChatGPT account**:

```sh
codex --version
codex app-server --help
codex login
codex login status
```

Complete the browser login flow described in the [official authentication guide](https://learn.chatgpt.com/docs/auth). Choose ChatGPT login for this POC. Do not configure an API key for this app. A successful login check confirms authentication, not this app's Plus/allowance conditions; the app checks those again when you request AI work.

The bridge prefers the Codex binary bundled with the macOS ChatGPT app at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`. Otherwise it uses `codex` on PATH. That bundled binary and a separately installed CLI may have different versions. Installing the CLI alone does not replace the desktop bundle the bridge prefers. See the compatibility troubleshooting entry below if needed.

You do not need to start `codex app-server` yourself or keep the Codex main window open. The Python backend starts and stops a child process for each AI request. There is no additional AI HTTP server to configure.

### 4. Start the local application

From the project folder:

```sh
python3 server.py
```

Expected startup output includes:

```text
Explanatory Learning App (POC) started: http://127.0.0.1:8767/
Data file: .../data/poc-library.sqlite3
```

Open **http://127.0.0.1:8767/** if the browser does not open automatically. You should see **Explanatory Learning App**, an empty card library, **New topic**, and **New card**. A normal startup does not call AI or consume subscription allowance.

On macOS you can instead double-click `Start.command`, or run:

```sh
bash Start.command
```

The launcher first checks `/usr/local/bin/python3`, then Python on PATH. If the launcher selects an old interpreter, run the application explicitly with the Python executable that passed step 2 instead.

Keep the Terminal/launcher window open while using the app. Press **Control+C** in that window to stop it. To start again later, run the same command or double-click `Start.command`; your saved data will be reopened. Do not launch a second copy on the same port.

### 5. Change the port or data location when needed

If another program is using port 8767:

```sh
python3 server.py --port 8768
```

Open the new URL printed by the program. Additional options:

| Option | Example | Effect |
| --- | --- | --- |
| `--port` | `python3 server.py --port 8768` | Use a different local port. |
| `--no-browser` | `python3 server.py --no-browser` | Start without automatically opening a browser. |
| `--db` | `python3 server.py --db ./my-library/library.sqlite3` | Use a separate library. Parent folders are created; images and request logs are stored beside this database. |
| `--preferences-dir` | `python3 server.py --preferences-dir ./local-preference-notes` | Change where this app writes explicitly confirmed preference notes. This does **not** isolate or disable Codex's own enabled memory. |

The same options work after `bash Start.command`. `python3 server.py --help` lists them without starting the web server or calling AI.

The server listens only on `127.0.0.1`: it is for the same computer's browser. Do not expose this POC through a public tunnel or change it into a public multi-user service.

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

Runtime data is created under `data/` and excluded from Git. Refreshing/restarting does not reimport the empty seed over an existing database. To back up, stop the program and copy `data/` (or the database directory selected with `--db`). Keep shared Codex preference notes separately if you use them. To restore, stop the app, keep a copy of the current data, and put your backup back at the same path before restarting. Do not copy a live SQLite file while writes are in progress. Copying the repository alone does not copy your library. App updates should retain this data directory; the empty seed is used only when creating a new database.

Messages, questions, choices, plans, candidate versions, and adoption records are saved. Failed tasks retain requirements and earlier checkpoints and give recovery actions. Pending messages and stale card/topic/graph versions prevent adopting an older result over newer work. History supports traceability; there is no one-click rollback interface.

Only submitted information is persisted. Unsent input stays in the page, with leave warnings where supported. Candidate validity, matching quotations, and successful saves do not prove factual accuracy or learning effectiveness. Review content before adopting it.

## Troubleshooting

| What you see | What to do next |
| --- | --- |
| `python3: command not found` or Python older than 3.11 | Install Python 3.11+ from [python.org](https://www.python.org/downloads/), reopen Terminal, and repeat step 2. Do not assume the operating system's Python is suitable. |
| `No module named tomllib` | You are using Python older than 3.11. Use the interpreter that passed the prerequisite check. No `pip install` is needed for the supported runtime. |
| `No module named sqlite3` | This Python distribution lacks SQLite support. Use a Python distribution with the standard SQLite module, then repeat step 2. |
| `ZoneInfoNotFoundError` for `Asia/Shanghai` | The Python environment cannot find the timezone data used by this POC. Use a Python/OS installation with timezone data and repeat step 2. Native Windows installation has not been verified. |
| Double-clicking `Start.command` does not start the app | Open Terminal in the project directory and run `bash Start.command`, or run `python3 server.py` with the verified interpreter. Read the printed error before retrying. |
| Port in use / page cannot start | Check whether you already started a copy. Reuse that window, stop it with Control+C, or start with `--port 8768` and open the printed URL. |
| Browser cannot connect | Keep the Python terminal open. Open the exact `http://127.0.0.1:PORT/` URL printed there. Do not use a `file://` URL or just run `python3 -m http.server`; the app needs its backend. |
| Codex not found | Install the CLI, reopen Terminal, and confirm `codex --version` works. Manual functions remain available without Codex. |
| Sign-in is not confirmed as Plus | Check `codex login status` and sign in using your own ChatGPT Plus account. Other account types are intentionally rejected by this app's current subscription-only guard. |
| Allowance exhausted, unknown, or extra credits present | No AI request is sent when the check blocks it. Wait for included allowance to recover or inspect your account status; do not buy credits to bypass this POC's guard. |
| Codex connection/protocol/model error after installation or update | Check the version selected by the bridge. On macOS, the ChatGPT desktop bundle takes priority over CLI on PATH. Its version can be checked using the quoted bundled path above followed by `--version`. Capture the error and relevant version for the maintainer; do not change billing/authentication paths as a workaround. |
| Generation times out or a batch fails | Open the generation record. Saved checkpoints and requirements are retained. Explicitly continue remaining cards or return to the confirmed outline. Failed tasks do not automatically retry. |
| Candidate cannot be adopted after edits elsewhere | Reopen the latest card/topic/graph and continue from current content. Stale-version protection prevents overwriting newer work. |
| A URL/image was saved but AI reports it could not read it | Review the original. Paste text or add a clearer screenshot, save references, and explicitly request the next generation. Saving alone does not prove reading. |
| Library is unexpectedly empty after restart | Check that you launched the same project folder with the same `--db` path. Different paths create independent libraries. Stop before moving/restoring files; keep the existing database. |

**Compatibility limit:** the Codex `app-server` command is experimental and may change. Official documentation describes its protocol and limitations in [Codex App Server](https://learn.chatgpt.com/docs/app-server). The current POC has no universal compatibility guarantee across Codex releases, account configurations, or operating systems. Authentication/help checks alone do not prove a real model turn works. Try a small outline as your first explicit AI request and review the result before requesting a large topic.

## How the local AI connection works

```text
Browser on your computer
  -> local HTTP request to Python
  -> installed Codex app-server child process (stdio / JSON messages)
  -> online model using your own ChatGPT login
  -> validated candidate saved locally and shown for review
  -> explicit adoption updates your saved library
```

The app stores its own discussions and sends relevant context with each request. It does not send messages into an existing desktop chat. It does not include the author's account, memory, or study library. Read [PRIVACY.md](PRIVACY.md) before using personal references.

## Repository boundaries

The root `.gitignore` uses an explicit release allowlist. Add new functional files deliberately after reviewing them. Keep generated content, credentials, local memory, personal references, development checks, and runtime output outside commits. The bundled empty `seed.json` is application initialization, not sample learning content.

Implementation boundaries and limits: [ARCHITECTURE.md](ARCHITECTURE.md). Bundled dependency attribution: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

This copy is English-first: interface text, interaction prompts, diagnostics, and documentation are English. User-authored content may use other languages; selected-text replacement follows the user's requested language. No account or study data is included.
