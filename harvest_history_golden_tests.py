#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import import_codex_history


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
GOLDEN_TESTS_PATH = DATA_DIR / "golden_tests.json"
HISTORY_TEST_SUMMARY_PATH = DATA_DIR / "history_golden_test_harvest.json"
SESSIONS_DIR = Path.home() / ".codex" / "sessions"
ARCHIVED_SESSIONS_DIR = Path.home() / ".codex" / "archived_sessions"

MAX_PROMPT_CHARS = 900
DEFAULT_LIMIT = 80

SENSITIVE_PATTERNS = (
    (re.compile(r"(?i)(password|passwd|pwd|token|api[_-]?key|secret)\s*[:=]\s*['\"]?[^\\s,'\"]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(bearer|sk-[a-z0-9_-]{8,})[a-z0-9._-]*"), "[REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED_PRIVATE_KEY]"),
)

SKIP_PREFIXES = (
    "<environment_context>",
    "<heartbeat>",
    "automation:",
    "automation id:",
    "run a metered",
    "assistant style:",
    "debian gnu/linux comes with absolutely no warranty",
)

QUESTION_STARTERS = (
    "can you",
    "will you",
    "would you",
    "what",
    "how",
    "why",
    "where",
    "when",
    "which",
    "please",
    "i need",
    "lets",
    "let's",
    "fix",
    "diagnose",
    "search",
    "compare",
    "design",
    "create",
    "make",
    "write",
    "upload",
    "update",
    "install",
    "look at",
)

ARTIFACT_OR_CHANGE_TERMS = (
    "create",
    "make",
    "write",
    "build",
    "generate",
    "update",
    "fix",
    "upload",
    "save",
    "install",
    "download",
    "pull",
    "set up",
)

BASE_FORBIDDEN_TERMS = [
    "run failed",
    "no final message returned",
    "no response",
    "load failed",
    "recovery plan:",
    "i do not have access",
    "i don't have access",
    "you can check it yourself",
]


def compact(text, limit=MAX_PROMPT_CHARS):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 12].rstrip() + " [truncated]"


def redact(text):
    clean = str(text or "")
    if "Public web context:" in clean:
        clean = clean.split("Public web context:", 1)[0].rstrip()
    for pattern, replacement in SENSITIVE_PATTERNS:
        clean = pattern.sub(replacement, clean)
    return clean


def normalized_key(text):
    text = redact(text).lower()
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"/users/[^\s]+", " /path ", text)
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", " ip ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def test_id_for_prompt(prompt):
    digest = hashlib.sha1(normalized_key(prompt).encode("utf-8")).hexdigest()[:14]
    return f"history-{digest}"


def is_testable_prompt(text):
    stripped = compact(text, 2000)
    lower = stripped.lower()
    if not stripped or len(stripped) < 14:
        return False
    if lower in {"are you there?", "thank you", "thanks", "awesome", "perfect", "lets do it", "let's do it"}:
        return False
    if re.match(r"^[a-z_][a-z0-9_-]*@[^:]+[:$]", lower) and not any(lower.startswith(starter) for starter in QUESTION_STARTERS):
        return False
    if lower.startswith("failed: traceback") and "can you" not in lower and "will you" not in lower:
        return False
    if lower.startswith("-") and "?" not in lower:
        return False
    if re.match(r"^\d{1,2}:\d{2}\s*(?:am|pm)\s+", lower):
        return False
    if lower.startswith("done. http") and "?" not in lower:
        return False
    if "translated report" in lower[:120] and "exception type:" in lower and "crashed thread:" in lower:
        return False
    if "private startup inventory:" in lower or "current request analysis:" in lower:
        return False
    if any(lower.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False
    if any(term in lower for term in ("see attached", "see photos", "see photo", "attached image", "attached is", "based on the image", "from this image")):
        return False
    if re.search(r"\b(?:img[_-]?\d+|screenshot|photo)\.(?:jpe?g|png|heic|webp)\b", lower):
        return False
    if lower.startswith("# files mentioned by the user:") and "my request for codex:" not in lower:
        return False
    if len(stripped) < 170 and any(term in lower for term in ("before we move on", "fix this properly")):
        return False
    if lower.count("\n") > 35 and "my request for codex:" not in lower:
        return False
    if len(stripped) > 5000:
        return False
    return "?" in stripped or any(lower.startswith(starter) for starter in QUESTION_STARTERS)


def quality_score(text):
    lower = text.lower()
    score = 0
    if "?" in text:
        score += 8
    if len(text) >= 60:
        score += 8
    if len(text) >= 160:
        score += 6
    domain_terms = (
        "qidi", "rat rig", "ratrig", "klipper", "moonraker", "marlin", "orca",
        "filament", "cad", "fusion", "stl", "cfd", "fea", "wiring", "diagram",
        "solar", "battery", "codex cli ui", "github", "flight ops", "tinmanx",
        "xfoil", "openvsp", "su2", "qblade", "graphviz",
    )
    score += min(40, sum(6 for term in domain_terms if term in lower))
    if any(term in lower for term in ("not acceptable", "failure", "failed", "didnt", "didn't", "fix this", "your son")):
        score += 18
    if any(term in lower for term in ("search the web", "current", "latest", "price", "availability")):
        score += 10
    if any(term in lower for term in ("thank", "awesome", "perfect", "brother")) and len(text) < 80:
        score -= 20
    return score


def project_for_prompt(text):
    lower = text.lower()
    if any(term in lower for term in ("codex cli ui", "codex cli", "ollama", "heartbeat", "github", "dock", "app icon")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("wiring diagram", "block diagram", "electrical diagram", "schematic", "power diagram", "graphviz")):
        return "engineering-diagrams"
    if "cpap hose" in lower and any(term in lower for term in ("inner diameter", "id", "inside diameter")):
        return "research-parts-reference"
    if any(term in lower for term in ("wind turbine", "alternator", "generator", "60vdc", "60 vdc", "300 rpm", "solar", "battery", "charge controller", "inverter", "off-grid", "3 phase", "split phase")):
        return "energy-power-research"
    if any(term in lower for term in ("tinmanx", "rocket slicer", "orca", "filament profile", "temp tower", "pressure advance", "pet-cf", "pctg", "slicer", "tinmanx1")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("fusion", "freecad", "cad", "stl", "step", "cpap duct", "cooling duct", "fea", "structural", "xfoil", "openvsp", "su2", "qblade")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("qidi", "rat rig", "ratrig", "klipper", "moonraker", "marlin", "prusa", "bambu", "sovol", "centauri", "printer")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("price", "availability", "buy", "compare pricing", "generator", "alternator", "part number")):
        return "research-parts-reference"
    if any(term in lower for term in ("flight ops", "flightops", "pilot", "aircraft", "certificate", "customer", "service charge", "service fee", "services charge", "services charges", "wb air")):
        return "flightops-tracker"
    return ""


def web_needed(text):
    lower = text.lower()
    return any(term in lower for term in ("search the web", "current", "latest", "today", "price", "availability", "github", "download", "manual"))


def required_terms_for_prompt(text, project_id=""):
    lower = text.lower()
    required = []
    cpap_hose_spec = "cpap hose" in lower and any(term in lower for term in ("inner diameter", "id", "inside diameter"))
    artifact_or_change = any(term in lower for term in ARTIFACT_OR_CHANGE_TERMS)
    if not artifact_or_change and any(term in lower for term in ("best", "recommend", "should i", "what is the best")):
        required.extend(["this is why", "you should also consider"])
    if project_id == "tinmanx-slicer-research" and ("filament" in lower or "temp tower" in lower):
        required.append("filament")
    if "marlin" in lower:
        required.append("marlin")
    if "klipper" in lower:
        required.append("klipper")
    if "fusion" in lower and not cpap_hose_spec:
        required.append("fusion")
    if "cfd" in lower:
        required.append("cfd")
    if "web" in lower or "price" in lower or "availability" in lower:
        required.append("http")
    return list(dict.fromkeys(required))[:6]


def golden_test_from_prompt(prompt, source):
    prompt = compact(redact(prompt), MAX_PROMPT_CHARS)
    project_id = project_for_prompt(prompt)
    test = {
        "id": test_id_for_prompt(prompt),
        "name": compact(prompt, 58),
        "group": "Slow",
        "prompt": prompt,
        "profile": "manager",
        "managerDepth": "fast",
        "webSearch": "live" if web_needed(prompt) else "disabled",
        "expectedProjectId": project_id,
        "directAnswer": bool(re.match(r"(?i)^(what|which|can you tell|what is the best|how can|how do)", prompt)),
        "directTerms": [],
        "requiredTerms": required_terms_for_prompt(prompt, project_id=project_id),
        "anyTerms": [],
        "forbiddenTerms": BASE_FORBIDDEN_TERMS,
        "requiresSource": bool(web_needed(prompt)),
        "minAnalyticalScore": 74,
        "goal": "Real chat-history regression: answer Tinman's actual prompt without cold fallback, wrong routing, or fake completion.",
        "source": "history-harvest",
        "historySource": source,
        "qualityScore": quality_score(prompt),
        "createdAt": time.time(),
        "updatedAt": time.time(),
    }
    if not test["expectedProjectId"]:
        test.pop("expectedProjectId")
    if not test["requiredTerms"]:
        test.pop("requiredTerms")
    if not test["requiresSource"]:
        test.pop("requiresSource")
    return test


def session_paths():
    paths = []
    if SESSIONS_DIR.exists():
        paths.extend(SESSIONS_DIR.glob("**/*.jsonl"))
    if ARCHIVED_SESSIONS_DIR.exists():
        paths.extend(ARCHIVED_SESSIONS_DIR.glob("*.jsonl"))
    return sorted(set(paths))


def split_embedded_user_turns(text):
    text = str(text or "")
    if not re.search(r"(?m)^User:\s*", text) or not re.search(r"(?m)^Assistant:\s*", text):
        return [text]
    turns = []
    for match in re.finditer(r"(?ms)^User:\s*(.*?)(?=^Assistant:|^User:|\Z)", text):
        chunk = match.group(1).strip()
        if chunk:
            turns.append(chunk)
    return turns or [text]


def iter_user_messages(path):
    session_id = path.stem
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_type = item.get("type")
            payload = item.get("payload") or {}
            if item_type == "session_meta":
                session_id = payload.get("id") or payload.get("session_id") or session_id
                continue
            if item_type != "response_item" or payload.get("type") != "message" or payload.get("role") != "user":
                continue
            text = import_codex_history.normalize_text(import_codex_history.extract_text(payload.get("content")))
            if import_codex_history.is_noise(text):
                continue
            for turn in split_embedded_user_turns(text):
                yield turn, session_id


def prompt_candidates():
    for path in session_paths():
        for text, session_id in iter_user_messages(path):
            if is_testable_prompt(text):
                yield text, f"{path.name}:{session_id}"


def load_golden_data():
    if GOLDEN_TESTS_PATH.exists():
        try:
            data = json.loads(GOLDEN_TESTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("version", 1)
                data.setdefault("createdAt", time.time())
                data.setdefault("tests", [])
                return data
        except Exception:
            pass
    now = time.time()
    return {"version": 1, "createdAt": now, "updatedAt": now, "tests": []}


def harvest(limit=DEFAULT_LIMIT, dry_run=False, replace_history=False):
    seen = set()
    tests = []
    for prompt, source in prompt_candidates():
        key = normalized_key(prompt)
        if not key or key in seen:
            continue
        seen.add(key)
        tests.append(golden_test_from_prompt(prompt, source))

    data = load_golden_data()
    removed = 0
    if replace_history:
        original_count = len(data.get("tests", []))
        data["tests"] = [item for item in data.get("tests", []) if item.get("source") != "history-harvest"]
        removed = original_count - len(data["tests"])
    existing = {item.get("id"): item for item in data.get("tests", []) if item.get("id")}
    tests.sort(key=lambda item: (-int(item.get("qualityScore") or 0), item.get("expectedProjectId", ""), item["name"].lower()))
    new_tests = [item for item in tests if item["id"] not in existing]
    old_tests = [item for item in tests if item["id"] in existing]
    selected = (new_tests + old_tests)[: max(0, int(limit or 0))]
    added = 0
    updated = 0
    for test in selected:
        old = existing.get(test["id"])
        if old:
            created = old.get("createdAt") or test["createdAt"]
            old.update(test)
            old["createdAt"] = created
            old["updatedAt"] = time.time()
            updated += 1
        else:
            data["tests"].append(test)
            existing[test["id"]] = test
            added += 1

    data["tests"] = sorted(data.get("tests", []), key=lambda item: (item.get("group", ""), item.get("name", "")))
    data["updatedAt"] = time.time()

    summary = {
        "harvestedAt": datetime.now(timezone.utc).isoformat(),
        "sessionFiles": len(session_paths()),
        "candidatePrompts": len(tests),
        "selectedTests": len(selected),
        "added": added,
        "updated": updated,
        "removedHistoryTests": removed,
        "dryRun": dry_run,
        "goldenTestsPath": str(GOLDEN_TESTS_PATH),
        "summaryPath": str(HISTORY_TEST_SUMMARY_PATH),
    }
    if selected:
        summary["sampleTests"] = [{"id": item["id"], "name": item["name"], "project": item.get("expectedProjectId", "")} for item in selected[:10]]

    if not dry_run:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        GOLDEN_TESTS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        HISTORY_TEST_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Harvest private Codex chat prompts into local golden tests.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum tests to add/update this run.")
    parser.add_argument("--dry-run", action="store_true", help="Scan and summarize without writing data/golden_tests.json.")
    parser.add_argument("--replace-history", action="store_true", help="Remove prior history-harvest tests before adding the new selected batch.")
    args = parser.parse_args()
    print(json.dumps(harvest(limit=args.limit, dry_run=args.dry_run, replace_history=args.replace_history), indent=2))


if __name__ == "__main__":
    main()
