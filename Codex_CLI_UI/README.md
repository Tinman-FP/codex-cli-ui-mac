# Codex CLI UI

A local Mac UI for the bundled Codex CLI and the local Ollama profiles.

## Run

```bash
cd ~/Applications/Codex_CLI_UI
python3 server.py
```

Open:

```text
http://127.0.0.1:8765
```

Or launch the standalone Mac app:

```bash
open -a "Codex CLI UI"
```

The standalone app is a native AppKit/WebKit wrapper. It opens Codex CLI UI in its own window, starts `server.py` if the local service is not already running, and only uses the system browser when you click an external source link.

## Native App Build

```bash
cd ~/Applications/Codex_CLI_UI
mkdir -p build
clang -fobjc-arc -framework Cocoa -framework WebKit native/CodexCLIUI.m -o build/CodexCLIUI
```

Install by copying `build/CodexCLIUI`, `native/Info.plist`, and `Resources/applet.icns` into a standard `.app` bundle with `CFBundleExecutable` set to `CodexCLIUI`, then sign it:

```bash
codesign --force --deep --sign - "/Applications/Codex CLI UI.app"
```

## Environment Overrides

```bash
CODEX_PROFILE=local-oss CODEX_CWD="$HOME/Documents/Codex" python3 server.py
```

The server binds to `127.0.0.1` by default and streams `codex exec --json` output to the browser.

## Modes

- `Manager` is the default. It routes each request to a project specialist, runs the worker answer through local `Review`, then uses local `gpt-oss-20b` to polish the final answer.
- `Manager` speed can be set to `Fast`, `Balanced`, or `Full`. Fast skips the second pass, Balanced uses shorter local review/polish budgets, and Full uses the deeper local review/polish path.
- `Fast` uses `local-fast`, low reasoning, and a shorter imported-history context.
- `Careful` uses `local-oss`, medium reasoning, and deeper imported-history context.
- `Coder` uses `local-coder` with the free local Ollama `qwen2.5-coder-7b` alias. Use it for implementation-heavy app, script, and repo work.
- `Review` uses direct local Ollama with the free `deepseek-r1-8b` alias. Use it for second opinions, bug hunts, and response-quality checks.
- `Local Research` searches free public web pages, caches evidence locally in SQLite, then asks the local Ollama `gpt-oss-20b` model to write the grounded answer. This is the preferred no-pay path for shopping, part matching, current specs, and product research.
- `Cloud Research` uses the OpenAI Responses API for public web/general research when `OPENAI_API_KEY` is configured. It is disabled by default in free-only mode. It does not include the private startup inventory, machine list, SSH aliases, or local project history in the cloud prompt.
- The UI passes the `Web` setting into each run. Local Codex can use it as a hint; Local Research requires it to be on.
- The composer keeps the prompt box above a compact one-row options bar for `Mode`, `Access`, `Reasoning`, `Friendly`, `Humor`, and `Web`.
- `Friendly` can be set to `Focused`, `Warm`, or `High`; `Humor` can be set to `Off`, `Light`, or `Playful`. The server keeps humor out of safety-critical, legal, medical, financial, printer-control, password, and precision troubleshooting answers.
- `Manager` Balanced/Full now runs a local Quality Coach pass after review/polish. The rubric favors direct answers, clear picks, `This is why:`, practical caveats, source grounding for current facts, and clean formatting.
- Finished assistant replies include local `Good` and `Fix this` feedback actions. Feedback is stored in `data/quality_feedback.jsonl` and reused as project-specific answer-quality lessons.
- `Fix this` feedback and capability gaps now flow into the Admin `Improvement Lab`, where they can be reviewed, archived, or promoted into regression-test candidates.
- Tool/run failures now have a recovery path. If the local worker hits a load failure or returns no final answer, the UI/server produce a useful recovery answer that says what failed, what was not confirmed, and the next concrete fallback instead of ending with raw `Run failed` text.
- The Tool Recovery Engine classifies failures such as missing commands, missing Git remotes, disabled web paths, Klipper config discovery gaps, local load failures, and permission boundaries, then chooses a free/safe recovery path before retry guidance.
- The capability manager lets local Codex notice missing free tools, inspect an allowlisted installer catalog, check available storage, install small/free tools through Homebrew, then retry the job. It asks before paid, unknown, large, or low-storage downloads.
- Local Klipper tools can discover `printer.cfg` config folders, identify Moonraker targets, and stage Klipper-safe macros locally. Live upload/restart still requires explicit intent and idle/standby verification.
- The analytical layer runs before answers and tool use. It classifies the domain, platform, firmware, operating system, framework, material, or protocol; picks the right tool family; names missing evidence; and avoids wrong-ecosystem mistakes such as using Klipper tools on a Marlin/Prusa printer.
- The self-learning layer stores compact durable lessons, procedures, formulas, local paths, and source pointers while rejecting volatile facts such as current prices, latest specs, live printer status, news, schedules, and secrets.
- The right rail includes a live `Model Health` graph for Ollama, model stack, Manager pass timing, memory, disk, load, and Qidi reachability.
- Active runs show concise `Working notes` in the assistant message while Codex is thinking and using tools.
- The `Admin` screen includes topic cleanup, stable knowledge Promote/Delete controls, the Improvement Lab, model warmup, performance benchmark runs, and a package health check.

Terminal shortcuts:

```bash
codex-fast
codex-careful
```

## Import Codex History

```bash
cd ~/Applications/Codex_CLI_UI
python3 import_codex_history.py
```

This creates a compact local index in `data/` from `~/.codex/sessions`. The UI server injects relevant history snippets into new Codex runs.

## Hybrid Cloud Research Setup

The official OpenAI CLI is installed with Homebrew:

```bash
openai --version
```

To enable `Cloud Research` mode for the LaunchAgent-backed UI:

```bash
launchctl setenv CODEX_FREE_ONLY 0
launchctl setenv OPENAI_API_KEY <your-api-key>
launchctl kickstart -k gui/$(id -u)/com.tinmanfp.codex-cli-ui
```

Do not paste API keys into chat. Local Codex modes remain the right choice for files, shell commands, printers, VPN devices, SSH, and private Mac context.

## Local Research

`Local Research` does not require an OpenAI API key. It uses DuckDuckGo/Bing HTML search, direct page fetches, a 24-hour local cache at `data/local_research_cache.sqlite3`, and Ollama on `127.0.0.1:11434`.

Free local model installs used by the full no-pay setup:

```bash
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:8b
ollama pull gpt-oss:20b
ollama cp qwen2.5-coder:7b qwen2.5-coder-7b
ollama cp deepseek-r1:8b deepseek-r1-8b
ollama cp gpt-oss:20b gpt-oss-20b
```

Optional model override:

```bash
launchctl setenv LOCAL_RESEARCH_MODEL gpt-oss-20b
launchctl setenv LOCAL_CODER_MODEL qwen2.5-coder-7b
launchctl setenv LOCAL_REVIEW_MODEL deepseek-r1-8b
launchctl setenv MANAGER_POLISH_MODEL gpt-oss-20b
launchctl setenv CODEX_PREWARM_MODELS gpt-oss-20b
launchctl setenv CODEX_MANAGER_DEPTH balanced
launchctl kickstart -k gui/$(id -u)/com.tinmanfp.codex-cli-ui
```

Keep the `Web` toggle on for this mode. Turn it off when you want a fully offline local Codex run.

The local Codex profiles use `~/.codex/model-catalogs/local-oss.json` so Codex has context metadata for `gpt-oss-20b` and `qwen2.5-coder-7b` instead of falling back to unknown-model defaults.

The app also has a local Python environment with `openai`, `openai-agents`, `openai-codex`, and `python-dotenv` staged for a fuller manager-agent workflow. `openai-codex` gives us a cleaner future path to drive Codex programmatically.

Pre-package check:

```bash
python3 checks/verify_package_health.py
```

Local tool API examples:

```bash
curl http://127.0.0.1:8765/api/tools/capabilities
curl "http://127.0.0.1:8765/api/tools/klipper-configs?hint=qidi"
curl -X POST http://127.0.0.1:8765/api/tools/install-free-tool \
  -H 'Content-Type: application/json' \
  -d '{"tool":"jq","reason":"parse Moonraker API JSON"}'
curl -X POST http://127.0.0.1:8765/api/tools/recover \
  -H 'Content-Type: application/json' \
  -d '{"error":"/bin/bash: jq: command not found","messages":[{"role":"user","text":"Parse this Moonraker JSON"}]}'
```

```bash
~/Applications/Codex_CLI_UI/.venv/bin/python
```
