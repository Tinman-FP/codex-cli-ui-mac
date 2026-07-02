#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
SESSIONS_DIR = Path.home() / ".codex" / "sessions"
MEMORY_PATH = Path.home() / ".codex" / "memories" / "MEMORY.md"
INDEX_PATH = DATA_DIR / "codex_history_index.jsonl"
SUMMARY_PATH = DATA_DIR / "codex_history_summary.json"

MAX_MESSAGE_CHARS = 6000
MAX_SESSION_DOCS = 80
NOISE_PREFIXES = (
    "<environment_context>",
    "<developer",
    "<skills_instructions>",
    "<plugins_instructions>",
    "<permissions instructions>",
)


def extract_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("input_text") or item.get("output_text")
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def normalize_text(text):
    text = re.sub(r"\r\n?", "\n", text or "").strip()
    request_marker = "## My request for Codex:"
    if request_marker in text:
        text = text.split(request_marker, 1)[1].strip()
    if text.startswith("Continue this local Codex CLI conversation."):
        marker = "Conversation:\n"
        if marker in text:
            text = text.split(marker, 1)[1].strip()
    return text


def is_noise(text):
    stripped = (text or "").lstrip()
    if not stripped:
        return True
    if any(stripped.startswith(prefix) for prefix in NOISE_PREFIXES):
        return True
    if stripped.startswith("# AGENTS.md instructions") or "<INSTRUCTIONS>" in stripped[:2000]:
        return True
    if stripped.startswith("# Browser Safety") or stripped.startswith("# Browser Capability:"):
        return True
    if "You are Codex, a coding agent" in stripped[:3000]:
        return True
    if "You are a coding agent running in the Codex CLI" in stripped[:3000]:
        return True
    return False


def title_from_messages(messages):
    for message in messages:
        if message["role"] != "user":
            continue
        text = re.sub(r"\s+", " ", message["text"]).strip()
        if text:
            return text[:90]
    return "Codex session"


def read_session(path):
    meta = {
        "session_id": path.stem,
        "timestamp": "",
        "cwd": "",
        "source": "",
    }
    messages = []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            item_type = item.get("type")
            payload = item.get("payload") or {}
            if item_type == "session_meta":
                meta["session_id"] = payload.get("id") or payload.get("session_id") or meta["session_id"]
                meta["timestamp"] = payload.get("timestamp") or item.get("timestamp") or meta["timestamp"]
                meta["cwd"] = payload.get("cwd") or meta["cwd"]
                meta["source"] = payload.get("source") or meta["source"]
                continue

            if item_type != "response_item":
                continue

            if payload.get("type") != "message":
                continue
            role = payload.get("role")
            if role not in {"user", "assistant"}:
                continue

            text = normalize_text(extract_text(payload.get("content")))
            if is_noise(text):
                continue

            if len(text) > MAX_MESSAGE_CHARS:
                text = text[:MAX_MESSAGE_CHARS].rstrip() + "\n[truncated]"

            messages.append({"role": role, "text": text})
            if len(messages) >= MAX_SESSION_DOCS:
                break

    if not messages:
        return None

    return {
        "session_id": meta["session_id"],
        "timestamp": meta["timestamp"],
        "cwd": meta["cwd"],
        "source": meta["source"],
        "path": str(path),
        "title": title_from_messages(messages),
        "messages": messages,
    }


def session_to_documents(session):
    docs = []
    pair_index = 0
    messages = session["messages"]
    for index, message in enumerate(messages):
        if message["role"] != "user":
            continue
        assistant_text = ""
        if index + 1 < len(messages) and messages[index + 1]["role"] == "assistant":
            assistant_text = messages[index + 1]["text"]
        body = f"User: {message['text']}"
        if assistant_text:
            body += f"\nAssistant: {assistant_text}"
        docs.append(
            {
                "session_id": session["session_id"],
                "timestamp": session["timestamp"],
                "cwd": session["cwd"],
                "source": session["source"],
                "path": session["path"],
                "title": session["title"],
                "pair_index": pair_index,
                "text": body,
            }
        )
        pair_index += 1
    return docs


def memory_documents():
    if not MEMORY_PATH.exists():
        return []

    text = MEMORY_PATH.read_text(encoding="utf-8", errors="replace")
    chunks = []
    current = []
    for line in text.splitlines():
        if line.startswith("# Task Group:") and current:
            chunks.append("\n".join(current).strip())
            current = [line]
        elif line.startswith("# Task Group:") or current:
            current.append(line)
    if current:
        chunks.append("\n".join(current).strip())

    docs = []
    for index, chunk in enumerate(chunks):
        title = chunk.splitlines()[0].replace("# Task Group:", "").strip() or "Codex memory"
        docs.append(
            {
                "session_id": f"memory-{index}",
                "timestamp": "",
                "cwd": "",
                "source": "memory",
                "path": str(MEMORY_PATH),
                "title": title,
                "pair_index": index,
                "text": chunk[:MAX_MESSAGE_CHARS],
            }
        )
    return docs


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session_paths = sorted(SESSIONS_DIR.glob("**/*.jsonl"))
    documents = []
    imported_sessions = 0
    skipped_sessions = 0

    memory_docs = memory_documents()

    with INDEX_PATH.open("w", encoding="utf-8") as index_handle:
        for path in session_paths:
            session = read_session(path)
            if not session:
                skipped_sessions += 1
                continue
            imported_sessions += 1
            for document in session_to_documents(session):
                documents.append(document)
                index_handle.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")
        for document in memory_docs:
            documents.append(document)
            index_handle.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {
        "importedAt": datetime.now(timezone.utc).isoformat(),
        "sessionsDir": str(SESSIONS_DIR),
        "sourceSessionFiles": len(session_paths),
        "importedSessions": imported_sessions,
        "skippedSessions": skipped_sessions,
        "memoryDocuments": len(memory_docs),
        "documents": len(documents),
        "indexPath": str(INDEX_PATH),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
