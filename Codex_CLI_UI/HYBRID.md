# Codex CLI UI Hybrid Notes

## Current Shape

Codex CLI UI now has seven practical modes:

- `Manager`: default router. Chooses the project specialist and local/cloud engine, then runs local Review plus a local final polish pass.
- `Manager Speed`: `Fast`, `Balanced`, or `Full`; controls how much local second-pass work runs before the final answer.
- `Fast`: local Codex CLI, low reasoning, short project-history context.
- `Careful`: local Codex CLI, medium reasoning, deeper project-history context.
- `Coder`: local Codex CLI with Ollama alias `qwen2.5-coder-7b` for implementation-heavy work.
- `Review`: direct local Ollama with alias `deepseek-r1-8b` for second opinions, bug hunts, and response-quality checks.
- `Local Research`: free public web search and page fetches, local SQLite evidence cache, Ollama `gpt-oss-20b` synthesis.
- `Cloud Research`: optional paid OpenAI Responses API, public web/general research, no private startup inventory or local project-history injection. Disabled by default in free-only mode.
- `Friendly` and `Humor`: per-chat personality controls that tune final-answer warmth and light humor while preserving direct answers and serious-work guardrails.
- `Quality Coach`: local final-answer gate for Manager Balanced/Full. It checks directness, evidence, caveats, formatting, and project-specific answer shape before Tinman sees the final response.
- `Good` / `Fix this`: local feedback actions under assistant replies. They write compact lessons to `data/quality_feedback.jsonl` so future similar prompts can improve without re-teaching the same preference.
- `Improvement Lab`: Admin backlog fed by `Fix this` feedback, capability-manager gaps, and failing golden tests. Items can be reviewed, archived, or promoted into saved golden regression tests.
- `Golden Test Generator`: turns an Improvement Lab item into a runnable prompt test with route, source, direct-answer, required-term, and forbidden-word checks, then feeds failed runs back into the lab.
- `Failure Recovery`: local load/tool/runtime failures are converted into accountable recovery answers: blocker, unfinished/uncertain work, safe fallback, and next step. Raw `Run failed` text should not be the final user-facing answer.
- `Tool Recovery Engine`: classifies failure text and the original request, then chooses the recovery path for missing commands, missing Git remotes, disabled web, Klipper config discovery, local load failures, and permissions. It uses the same free-only storage and approval policy as Capability Manager.
- `Analytical Operating System`: every request is classified by domain/platform/tool family before answering. It explicitly catches wrong-ecosystem traps such as Marlin/Prusa vs Klipper, codebase framework mismatch, weak research evidence, and volatile facts that require refresh.
- `Capability Manager`: local missing-tool recovery. It checks what command/capability is missing, looks for a free allowlisted install path, checks disk space, installs only safe small/free tools automatically, and asks Tinman before paid, unknown, large, or low-storage downloads.
- `Klipper Tools`: local OS/platform helpers for Klipper printers. They discover config folders, inspect `printer.cfg`/macro/LED files, expose known Moonraker targets, and stage local macro files without uploading or restarting a live printer.
- `Self-Learning Filter`: stores durable stable lessons and rejects secrets, raw transcripts, live statuses, prices, latest/current facts, and other volatile data.

Use `Fast`, `Careful`, or `Coder` for local files, shell commands, printer/VPN work, SSH, GitHub publishing, app packaging, and anything that needs this Mac as the tool runner.

Use `Review` when Tinman wants a second pass on code, answer quality, safety, missing tests, or whether a recommendation actually answers the question.

Use `Local Research` first for shopping/spec research, current public web questions, broad product comparisons, part matching, and product recommendations when you want to avoid paid API use.

Use `Cloud Research` when you deliberately want OpenAI's hosted web-search/reasoning path and have `OPENAI_API_KEY` configured.

## Installed Pieces

- Official OpenAI CLI: `/opt/homebrew/bin/openai`
- Local Python agent environment: `$HOME/Applications/Codex_CLI_UI/.venv`
- Python packages staged there: `openai`, `openai-agents`, `openai-codex`, `python-dotenv`
- Local Research cache: `$HOME/Applications/Codex_CLI_UI/data/local_research_cache.sqlite3`
- Local Research model: `gpt-oss-20b` through Ollama on `127.0.0.1:11434`
- Local Coder model: `qwen2.5-coder-7b` through Ollama
- Local Review model: `deepseek-r1-8b` through Ollama
- Manager polish model: `gpt-oss-20b` through Ollama
- Admin performance tools: model warmup, performance benchmark, package health check, Improvement Lab review controls, golden-test promotion/results, and stable knowledge Promote/Delete controls.
- Local capability tools: `/api/tools/capabilities`, `/api/tools/recover`, `/api/tools/install-free-tool`, `/api/tools/klipper-configs`, and `/api/tools/klipper-accel-rgb`.
- Live health graph: `/api/health` feeds Ollama status, model count, loaded models, memory, disk, load, Qidi reachability, route history, and pass timing into the right rail.

## Manager Router

The first manager layer is deterministic and visible:

- Scores the latest request against the real local project buckets.
- Selects a specialist such as `Printer/Ops Specialist`, `FlightOps Specialist`, or `Energy Research Specialist`.
- Injects only the selected project's playbook and focused project history into local Codex runs.
- Shows the selected route in the assistant message as a small badge.
- Uses Local Research for public product/spec/parts research when web is enabled.
- Uses Cloud Research only when free-only mode is disabled and it is explicitly selected or configured as a paid fallback.
- In Manager mode, captures the primary worker answer, asks local Review for a second pass, and sends a polished final answer back to the chat.
- The right rail shows the active worker/review/polish timing while a run is in progress.
- Falls back to local Codex when web access is disabled or a request needs local files, printers, SSH, VPN devices, or this Mac.

Project buckets:

- Flight Ops Tracker
- Printer & Klipper Operations
- OrcaSlicer Codex
- TinManX, Rocket Slicer & Materials
- Codex CLI UI & Local Agent
- Mac System, Accounts & Network
- CAD & Modeling Projects
- Research, Parts & Cross-Reference
- Energy & Power Research
- Bible & KJV Study

## API Key

Local Research does not require an OpenAI API key.

Cloud Research requires an OpenAI API key in the UI service environment. Set it through `launchctl`, not through chat:

```bash
launchctl setenv CODEX_FREE_ONLY 0
launchctl setenv OPENAI_API_KEY <your-api-key>
launchctl kickstart -k gui/$(id -u)/com.localuser.codex-cli-ui
```

Optional model override:

```bash
launchctl setenv OPENAI_RESEARCH_MODEL gpt-5.5
launchctl setenv LOCAL_RESEARCH_MODEL gpt-oss-20b
launchctl setenv LOCAL_CODER_MODEL qwen2.5-coder-7b
launchctl setenv LOCAL_REVIEW_MODEL deepseek-r1-8b
launchctl setenv MANAGER_POLISH_MODEL gpt-oss-20b
launchctl setenv CODEX_PREWARM_MODELS gpt-oss-20b
launchctl setenv CODEX_MANAGER_DEPTH balanced
launchctl kickstart -k gui/$(id -u)/com.localuser.codex-cli-ui
```

## Next Architecture Step

The fuller combined platform should be a manager-agent workflow:

- Manager agent owns the final answer and user tone.
- Quality Coach owns the final answer rubric and Tinman's saved feedback lessons.
- Improvement Lab owns turning weak-answer feedback, tool gaps, and regression failures into a visible backlog of fixes.
- Golden Test Generator owns converting those lessons into saved prompt tests so the same weakness can be rerun instead of rediscovered.
- Analytical Operating System owns domain/platform/tool-family classification before any answer or tool choice.
- Failure Recovery owns action accountability when a local tool, stream, file load, or runtime step breaks.
- Tool Recovery Engine owns mapping those failures to safe tools, local endpoints, approvals, and retry instructions.
- Capability Manager owns missing-tool detection, free-tool installation decisions, storage checks, and retry guidance.
- Klipper Tools own printer OS/platform tasks across Qidi, RatRig, Snapmaker, and other Moonraker/Klipper machines.
- Local Research agent handles no-pay public search, evidence extraction, source ranking, and Ollama synthesis.
- Cloud Research agent remains the optional paid path for OpenAI-hosted public facts, citations, shopping/spec checks, and general reasoning.
- Codex agent runs through Codex CLI or Codex MCP for local files, shell, repos, printers, and Mac workflows.

OpenAI's Agents SDK supports this with agents-as-tools and handoffs. Codex can also be exposed as an MCP server with `codex mcp-server`, so the manager can call Codex as a bounded local tool while keeping one coherent conversation.
