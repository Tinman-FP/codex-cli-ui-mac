"""Runtime binding and execution contract for registered capabilities.

Intent classification remains declarative in ``capability_registry``. This
module gives those declarations an executable boundary without importing HTTP,
model, tool, or product code.
"""

from __future__ import annotations

import hashlib
import html
import re
import shlex
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple


CapabilityContext = Mapping[str, Any]
CapabilityHandler = Callable[[CapabilityContext], Optional[Dict[str, Any]]]

EXECUTION_OUTCOMES = frozenset(
    {"completed", "bounded", "needs-input", "unhandled", "failed"}
)
HANDLED_OUTCOMES = frozenset({"completed", "bounded", "needs-input"})

_SHELL_NAMES = frozenset({"bash", "dash", "ksh", "sh", "zsh"})
_SHELL_SEPARATORS = frozenset({"|", "||", "&&", ";", "&"})
_PERSISTENT_REDIRECTIONS = frozenset({">", ">>", ">|", "<>", ">&", "&>", "&>>"})
_HEREDOC_REDIRECTIONS = frozenset({"<<", "<<-"})
_WRITE_COMMANDS = frozenset(
    {
        "chmod",
        "chgrp",
        "chown",
        "cp",
        "install",
        "ln",
        "mkdir",
        "mkfifo",
        "mknod",
        "mv",
        "patch",
        "rm",
        "rmdir",
        "tee",
        "touch",
        "truncate",
    }
)
_COMMAND_PREFIXES = frozenset({"builtin", "command", "env", "exec", "nohup", "sudo"})
_CAPABILITY_QUERY_RE = re.compile(
    r"\b(?:"
    r"do you (?:actually )?have (?:the |that )?capabilit(?:y|ies)|"
    r"are you (?:actually )?capable of|"
    r"is (?:that|this) something you (?:can|are able to) do|"
    r"i (?:am|'m) asking whether you (?:can|are able to|have)|"
    r"when i say .{0,80}\bi mean (?:whether |do )?you (?:can|have)|"
    r"do you support (?:doing |creating |designing |building )?"
    r")\b",
    flags=re.IGNORECASE | re.DOTALL,
)
_SOURCE_OBSERVATION_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", flags=re.IGNORECASE)
_SOURCE_OBSERVATION_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)
SOURCE_OBSERVATION_MAX_BYTES = 65536
_LOCAL_ACTION_RECEIPT_KINDS = frozenset(
    {
        "file-change",
        "focused-test",
        "file-rollback",
        "local-action-file-reconciliation",
        "local-action-proposal-normalization",
        "local-action-satisfaction-resolution",
        "local-action-source-satisfaction",
        "local-action-verified-noop",
    }
)
_LOCAL_ACTION_MUTATION_OPERATIONS = frozenset(
    {"change", "create", "delete", "draft", "edit", "fix"}
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def read_trusted_local_file_observation_text(path: Any) -> str:
    """Read one bounded, nonempty UTF-8 regular file for trusted evidence."""

    candidate = Path(_text(path)) if _text(path) else None
    if candidate is None or not candidate.is_file():
        return ""
    try:
        with candidate.open("rb") as handle:
            raw = handle.read(SOURCE_OBSERVATION_MAX_BYTES)
    except OSError:
        return ""
    if not raw or b"\x00" in raw:
        return ""
    try:
        text = raw.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        return ""
    if not text:
        return ""
    controls = sum(
        1
        for character in text
        if ord(character) < 32 and character not in "\n\r\t"
    )
    if controls > max(2, len(text) // 100):
        return ""
    return text


def normalize_source_observations(value: Any) -> tuple[list[Dict[str, Any]], list[str]]:
    """Validate trusted-reader observations before they cross executor boundaries."""

    candidates = value if isinstance(value, (list, tuple)) else []
    observations: list[Dict[str, Any]] = []
    issues: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, Mapping):
            issues.append(f"source-observation-{index}:invalid-type")
            continue
        source_type = _text(candidate.get("sourceType")).lower()
        path = _text(candidate.get("localPath") or candidate.get("path"))
        locator = _text(candidate.get("locator"))
        text = _text(
            candidate.get("text")
            or candidate.get("excerpt")
            or candidate.get("snippet")
            or candidate.get("proof")
        )
        content_sha256 = _text(candidate.get("contentSha256")).lower()
        observed_at = _text(candidate.get("observedAt"))
        candidate_issues = []
        if _text(candidate.get("kind")) != "source-observation":
            candidate_issues.append("invalid-kind")
        if source_type not in {"local-file", "runtime-state"}:
            candidate_issues.append("invalid-source-type")
        if source_type == "local-file":
            if not path or path.lower().startswith(("http://", "https://")):
                candidate_issues.append("invalid-local-path")
            observed_text = read_trusted_local_file_observation_text(path)
            if not observed_text:
                candidate_issues.append("missing-unreadable-binary-or-empty-file")
            elif text != observed_text:
                candidate_issues.append("observed-content-mismatch")
        elif source_type == "runtime-state":
            if not re.fullmatch(r"runtime://[a-z0-9][a-z0-9._/-]{1,120}", locator):
                candidate_issues.append("invalid-runtime-locator")
            if path:
                candidate_issues.append("runtime-state-has-local-path")
            if not _text(candidate.get("sourceId") or candidate.get("id")):
                candidate_issues.append("missing-runtime-source-id")
            if not text:
                candidate_issues.append("missing-runtime-observation")
        if not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(content_sha256):
            candidate_issues.append("invalid-content-hash")
        elif text and hashlib.sha256(text.encode("utf-8")).hexdigest() != content_sha256:
            candidate_issues.append("content-hash-mismatch")
        if not _SOURCE_OBSERVATION_TIMESTAMP_RE.fullmatch(observed_at):
            candidate_issues.append("invalid-observation-time")
        else:
            try:
                time.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                candidate_issues.append("invalid-observation-time")
        if candidate_issues:
            issues.extend(
                f"source-observation-{index}:{issue}" for issue in candidate_issues
            )
            continue
        normalized = {
            "kind": "source-observation",
            "sourceType": source_type,
            "text": text,
            "excerpt": text,
            "contentSha256": content_sha256,
            "observedAt": observed_at,
            "sourceId": _text(candidate.get("sourceId") or candidate.get("id")),
        }
        if source_type == "local-file":
            normalized.update({"path": path, "localPath": path})
        else:
            normalized["locator"] = locator
        observations.append(normalized)
    return observations, list(dict.fromkeys(issues))


def _missing_items(value: Any) -> list[str]:
    if value is None:
        candidates = []
    elif isinstance(value, (str, bytes)):
        candidates = [value]
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates = value
    else:
        candidates = []
    items = []
    seen = set()
    for candidate in candidates:
        item = _text(candidate)
        if item and item not in seen:
            items.append(item)
            seen.add(item)
    return items


def _return_code(value: Any) -> Tuple[int, str]:
    if value is None or value == "":
        return 0, ""
    try:
        code = int(value)
        if isinstance(value, bool) or (
            not isinstance(value, (str, bytes)) and value != code
        ):
            raise ValueError
        return code, ""
    except (TypeError, ValueError, OverflowError):
        return 1, f"Invalid capability return code `{_text(value) or type(value).__name__}`."


def _shell_tokens(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(
            html.unescape(_text(command)),
            posix=True,
            punctuation_chars="|&;<>",
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except (TypeError, ValueError):
        return []


def _nonpersistent_redirection_target(value: str) -> bool:
    target = _text(value)
    return bool(
        not target
        or target.isdigit()
        or re.fullmatch(r"&?\d+", target)
        or target in {"/dev/null", "/dev/stdout", "/dev/stderr"}
        or target.startswith("/dev/fd/")
    )


def _nested_shell_scripts(tokens: Sequence[str]) -> list[str]:
    scripts = []
    for index, token in enumerate(tokens):
        if token.rsplit("/", 1)[-1] not in _SHELL_NAMES:
            continue
        option_index = index + 1
        while option_index < len(tokens) and tokens[option_index].startswith("-"):
            option = tokens[option_index].lstrip("-")
            if "c" in option and option_index + 1 < len(tokens):
                scripts.append(tokens[option_index + 1])
                break
            option_index += 1
    return scripts


def inspect_shell_command(command: Any) -> Dict[str, Any]:
    """Detect persistent shell-write signals, including nested ``bash -lc`` scripts."""

    text = html.unescape(_text(command))
    tokens = _shell_tokens(text)
    signals = []
    redirections = []
    has_heredoc = False

    for index, token in enumerate(tokens):
        if token in _HEREDOC_REDIRECTIONS or token.startswith("<<"):
            has_heredoc = True
            signals.append("heredoc")
            continue
        if token not in _PERSISTENT_REDIRECTIONS:
            continue
        target = tokens[index + 1] if index + 1 < len(tokens) else ""
        if _nonpersistent_redirection_target(target):
            continue
        redirections.append({"operator": token, "target": target})
        signals.append("persistent-output-redirection")

    command_position = True
    active_command = ""
    for token in tokens:
        if token in _SHELL_SEPARATORS:
            command_position = True
            active_command = ""
            continue
        if command_position:
            if "=" in token and not token.startswith(("/", "./", "../")):
                continue
            name = token.rsplit("/", 1)[-1]
            if name in _COMMAND_PREFIXES:
                continue
            active_command = name
            command_position = False
            if name in _WRITE_COMMANDS:
                signals.append(f"write-command:{name}")
            continue
        if active_command in {"perl", "sed"} and token.startswith("-i"):
            signals.append(f"in-place-edit:{active_command}")

    nested = []
    for script in _nested_shell_scripts(tokens):
        nested_result = inspect_shell_command(script)
        nested.append(nested_result)
        signals.extend(nested_result.get("signals") or [])
        redirections.extend(nested_result.get("redirections") or [])
        has_heredoc = bool(has_heredoc or nested_result.get("hasHeredoc"))

    unique_signals = list(dict.fromkeys(_text(item) for item in signals if _text(item)))
    return {
        "writeDetected": any(
            signal != "heredoc" for signal in unique_signals
        ),
        "hasHeredoc": has_heredoc,
        "signals": unique_signals,
        "redirections": redirections,
        "nestedShellCount": len(nested),
    }


def latest_user_intent_text(messages: Any) -> str:
    if not isinstance(messages, (list, tuple)):
        return ""
    for message in reversed(messages):
        if not isinstance(message, Mapping):
            continue
        if _text(message.get("role")).lower() != "user":
            continue
        text = _text(message.get("text") or message.get("content"))
        if text:
            return " ".join(text.split())
    return ""


def intent_digest(value: Any) -> str:
    normalized = " ".join(_text(value).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def build_semantic_completion_receipt(
    messages: Any,
    summary: Any,
    evidence_receipt_ids: Sequence[Any],
    *,
    satisfied: bool = True,
) -> Dict[str, Any]:
    """Build a semantic receipt bound to the latest user turn, not an earlier task."""

    latest = latest_user_intent_text(messages)
    return {
        "kind": "semantic-completion",
        "intentDigest": intent_digest(latest),
        "satisfied": satisfied is True,
        "summary": _text(summary),
        "evidenceReceiptIds": [
            _text(item) for item in evidence_receipt_ids if _text(item)
        ],
    }


def _normalize_semantic_receipt(value: Any) -> Dict[str, Any]:
    receipt = value if isinstance(value, Mapping) else {}
    evidence_ids = receipt.get("evidenceReceiptIds")
    return {
        "kind": _text(receipt.get("kind")),
        "intentDigest": _text(receipt.get("intentDigest")),
        "satisfied": receipt.get("satisfied") is True,
        "summary": _text(receipt.get("summary")),
        "evidenceReceiptIds": _missing_items(evidence_ids),
    }


def _relative_receipt_paths(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else []
    paths = []
    for candidate in values:
        label = _text(candidate).replace("\\", "/")
        path = Path(label)
        if (
            not label
            or path.is_absolute()
            or ".." in path.parts
            or any(character in label for character in "*?[]{}")
        ):
            return []
        paths.append(path.as_posix())
    return list(dict.fromkeys(paths))


def _normalize_typed_local_action_receipt(
    candidate: Mapping[str, Any],
    index: int,
) -> Dict[str, Any]:
    """Validate metadata-only controller proof without requiring a shell command."""

    kind = _text(candidate.get("kind")).lower()
    status = _text(candidate.get("status")).lower()
    raw_exit = candidate.get("exitCode")
    exit_code, exit_error = _return_code(raw_exit)
    path_input = candidate.get("paths")
    if path_input is None and kind in {
        "local-action-proposal-normalization",
        "local-action-source-satisfaction",
    }:
        path_input = [candidate.get("path")]
    paths = _relative_receipt_paths(path_input)
    markers = _missing_items(candidate.get("mutationMarkers"))
    changed_paths = _relative_receipt_paths(candidate.get("changedPaths"))
    backup_paths = _relative_receipt_paths([candidate.get("backupPath")])
    issues = []
    verified = bool(
        candidate.get("verified") is True
        and raw_exit is not None
        and not exit_error
        and exit_code == 0
    )

    if kind == "file-change":
        before_sha = _text(candidate.get("beforeSha256")).lower()
        after_sha = _text(candidate.get("afterSha256")).lower()
        if status != "completed" or not verified:
            issues.append("controller-edit-not-verified")
        if len(paths) != 1:
            issues.append("controller-edit-path-invalid")
        if "controller-owned-edit" not in markers:
            issues.append("controller-edit-marker-missing")
        if (
            not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(before_sha)
            or not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(after_sha)
            or before_sha == after_sha
        ):
            issues.append("controller-edit-hash-invalid")
        if candidate.get("atomicWrite") is True:
            backup_sha = _text(candidate.get("backupSha256")).lower()
            binding_sha = _text(candidate.get("bindingSha256")).lower()
            request_sha = _text(candidate.get("requestSha256")).lower()
            binding_payload = {
                "afterSha256": after_sha,
                "backupPath": backup_paths[0] if len(backup_paths) == 1 else "",
                "backupSha256": backup_sha,
                "beforeSha256": before_sha,
                "changedPaths": changed_paths,
                "kind": kind,
                "path": paths[0] if len(paths) == 1 else "",
                "requestSha256": request_sha,
            }
            expected_binding_sha = hashlib.sha256(
                repr(sorted(binding_payload.items())).encode("utf-8")
            ).hexdigest()
            if (
                candidate.get("controllerOwned") is not True
                or candidate.get("contentsRecorded") is not False
                or len(backup_paths) != 1
                or backup_paths[0] == (paths[0] if len(paths) == 1 else "")
                or changed_paths != [
                    *(paths[:1]),
                    *(backup_paths[:1]),
                ]
            ):
                issues.append("controller-atomic-edit-metadata-invalid")
            if (
                not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(request_sha)
                or not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(backup_sha)
                or backup_sha != before_sha
            ):
                issues.append("controller-atomic-edit-backup-invalid")
            if (
                not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(binding_sha)
                or binding_sha != expected_binding_sha
            ):
                issues.append("controller-atomic-edit-binding-invalid")
    elif kind == "focused-test":
        if status != "passed" or not verified:
            issues.append("focused-test-not-passed")
        if not paths:
            issues.append("focused-test-surface-missing")
    elif kind == "file-rollback":
        after_sha = _text(candidate.get("afterSha256")).lower()
        restored_sha = _text(candidate.get("restoredSha256")).lower()
        if status != "completed" or not verified:
            issues.append("controller-rollback-not-verified")
        if len(paths) != 1:
            issues.append("controller-rollback-path-invalid")
        if "controller-owned-rollback" not in markers:
            issues.append("controller-rollback-marker-missing")
        if (
            not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(after_sha)
            or after_sha != restored_sha
        ):
            issues.append("controller-rollback-hash-invalid")
    elif kind == "local-action-verified-noop":
        request_sha = _text(candidate.get("requestSha256")).lower()
        source_sha = _text(candidate.get("sourceSha256")).lower()
        context_sha = _text(candidate.get("contextSha256")).lower()
        proposal_sha = _text(candidate.get("proposalSha256")).lower()
        context_start = candidate.get("contextStart")
        context_end = candidate.get("contextEnd")
        changed_paths = candidate.get("changedPaths")
        if (
            status != "verified"
            or not verified
            or candidate.get("result") != "requested-state-already-satisfied"
            or candidate.get("controllerOwned") is not True
            or candidate.get("sourceEvidenceVerified") is not True
            or candidate.get("sourceContentsRecorded") is not False
            or candidate.get("proposalContentsRecorded") is not False
        ):
            issues.append("verified-noop-receipt-invalid")
        if len(paths) != 1:
            issues.append("verified-noop-path-invalid")
        if not isinstance(changed_paths, (list, tuple)) or changed_paths:
            issues.append("verified-noop-has-changes")
        if markers:
            issues.append("verified-noop-has-mutation-marker")
        if not all(
            _SOURCE_OBSERVATION_SHA256_RE.fullmatch(value)
            for value in (request_sha, source_sha, context_sha, proposal_sha)
        ):
            issues.append("verified-noop-hash-invalid")
        if (
            type(context_start) is not int
            or type(context_end) is not int
            or context_start < 1
            or context_end < context_start
            or context_end - context_start + 1 > 60
        ):
            issues.append("verified-noop-context-invalid")
    elif kind == "local-action-source-satisfaction":
        source_hashes = (
            _text(candidate.get("requestSha256")).lower(),
            _text(candidate.get("typedRequestSha256")).lower(),
            _text(candidate.get("sourceSha256")).lower(),
            _text(candidate.get("contextSha256")).lower(),
            _text(candidate.get("verdictSha256")).lower(),
        )
        context_start = candidate.get("contextStart")
        context_end = candidate.get("contextEnd")
        if (
            status != "verified"
            or candidate.get("verified") is not True
            or candidate.get("verdict") != "satisfied"
            or candidate.get("controllerBound") is not True
            or candidate.get("verdictContentsRecorded") is not False
        ):
            issues.append("source-satisfaction-receipt-invalid")
        if len(paths) != 1:
            issues.append("source-satisfaction-path-invalid")
        if not all(
            _SOURCE_OBSERVATION_SHA256_RE.fullmatch(value)
            for value in source_hashes
        ):
            issues.append("source-satisfaction-hash-invalid")
        if (
            type(context_start) is not int
            or type(context_end) is not int
            or context_start < 1
            or context_end < context_start
            or context_end - context_start + 1 > 60
        ):
            issues.append("source-satisfaction-context-invalid")
        verified = not issues
    elif kind == "local-action-satisfaction-resolution":
        decision = _text(candidate.get("decision")).lower()
        planner_allowed = candidate.get("plannerAllowed") is True
        attempt_count = candidate.get("attemptCount")
        worker_count = candidate.get("workerInvocationCount")
        consistent_negative = candidate.get("consistentNegativeBinding") is True
        total_duration_ms = candidate.get("totalDurationMs")
        max_duration_ms = candidate.get("maxDurationMs")
        valid_decision = bool(
            (
                status == "verified-noop"
                and decision == "verified-noop"
                and not planner_allowed
                and type(attempt_count) is int
                and attempt_count in {1, 2}
            )
            or (
                status == "planner-allowed"
                and decision == "consistent-not-satisfied"
                and planner_allowed
                and attempt_count == 2
                and consistent_negative
            )
            or (
                status == "blocked"
                and decision not in {"verified-noop", "consistent-not-satisfied"}
                and not planner_allowed
                and type(attempt_count) is int
                and attempt_count in {1, 2}
            )
        )
        if (
            not verified
            or candidate.get("controllerOwned") is not True
            or candidate.get("contentsRecorded") is not False
            or not valid_decision
        ):
            issues.append("satisfaction-resolution-receipt-invalid")
        if (
            type(worker_count) is not int
            or worker_count < 0
            or type(attempt_count) is not int
            or worker_count > attempt_count
        ):
            issues.append("satisfaction-resolution-worker-count-invalid")
        if (
            type(total_duration_ms) is not int
            or type(max_duration_ms) is not int
            or total_duration_ms < 0
            or max_duration_ms <= 0
            or total_duration_ms > max_duration_ms
            or max_duration_ms > 45000
        ):
            issues.append("satisfaction-resolution-duration-invalid")
        verified = not issues
    elif kind == "local-action-proposal-normalization":
        if (
            status != "verified"
            or candidate.get("reasonCode") != "identical-edit-to-verified-noop"
            or candidate.get("inputKind") != "local-product-edit-proposal"
            or candidate.get("outputKind") != "local-product-verified-noop-proposal"
            or candidate.get("controllerBound") is not True
            or candidate.get("proposalContentsRecorded") is not False
        ):
            issues.append("noop-normalization-receipt-invalid")
        if len(paths) != 1:
            issues.append("noop-normalization-path-invalid")
        if not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(
            _text(candidate.get("proposalSha256")).lower()
        ):
            issues.append("noop-normalization-hash-invalid")
        if not _SOURCE_OBSERVATION_SHA256_RE.fullmatch(
            _text(candidate.get("outputProposalSha256")).lower()
        ):
            issues.append("noop-normalization-output-hash-invalid")
        verified = not issues
    elif kind == "local-action-file-reconciliation":
        changed_paths = candidate.get("changedPaths")
        if status != "verified" or not verified:
            issues.append("final-reconciliation-not-verified")
        if not isinstance(changed_paths, (list, tuple)) or changed_paths:
            issues.append("final-reconciliation-has-changes")
        if markers:
            issues.append("final-reconciliation-has-mutation-marker")

    return {
        "id": _text(candidate.get("id")) or f"local-action-{index}",
        "kind": kind,
        "command": _text(candidate.get("command")),
        "status": status,
        "exitCode": exit_code if raw_exit is not None else None,
        "verified": verified and not issues,
        "writeDetected": False,
        "writeSignals": [],
        "hasHeredoc": False,
        "paths": paths,
        "changedPaths": changed_paths,
        "backupPath": backup_paths[0] if len(backup_paths) == 1 else "",
        "mutationMarkers": markers,
        "controllerOwned": candidate.get("controllerOwned") is True,
        "atomicWrite": candidate.get("atomicWrite") is True,
        "beforeSha256": _text(candidate.get("beforeSha256")).lower(),
        "afterSha256": _text(candidate.get("afterSha256")).lower(),
        "backupSha256": _text(candidate.get("backupSha256")).lower(),
        "bindingSha256": _text(candidate.get("bindingSha256")).lower(),
        "testRun": candidate.get("testRun") is True,
        "testRequested": candidate.get("testRequested") is True,
        "requestSha256": _text(candidate.get("requestSha256")).lower(),
        "typedRequestSha256": _text(candidate.get("typedRequestSha256")).lower(),
        "sourceSha256": _text(candidate.get("sourceSha256")).lower(),
        "contextStart": candidate.get("contextStart"),
        "contextEnd": candidate.get("contextEnd"),
        "contextSha256": _text(candidate.get("contextSha256")).lower(),
        "proposalSha256": _text(candidate.get("proposalSha256")).lower(),
        "outputProposalSha256": _text(candidate.get("outputProposalSha256")).lower(),
        "issues": issues,
    }


def local_action_completion_proof_contract(
    command_receipts: Any,
    *,
    proof_requirements: Any = (),
    operation_plan: Any = None,
    completed: bool,
) -> Dict[str, Any]:
    """Require retained controller mutation, test, and reconciliation proof in order."""

    candidates = command_receipts if isinstance(command_receipts, (list, tuple)) else []
    requirements = set(_missing_items(proof_requirements))
    plan = operation_plan if isinstance(operation_plan, Mapping) else {}
    allowed = {_text(item).lower() for item in plan.get("allowedNow") or [] if _text(item)}
    mutation_authorized = bool(allowed.intersection(_LOCAL_ACTION_MUTATION_OPERATIONS))
    test_authorized = "test" in allowed
    typed = [
        _normalize_typed_local_action_receipt(candidate, index)
        for index, candidate in enumerate(candidates, start=1)
        if isinstance(candidate, Mapping)
        and _text(candidate.get("kind")).lower() in _LOCAL_ACTION_RECEIPT_KINDS
    ]
    applicable = bool(typed or requirements)
    issues = [
        issue
        for receipt in typed
        for issue in receipt.get("issues") or []
    ]
    edits = [item for item in typed if item.get("kind") == "file-change"]
    atomic_edits = [item for item in edits if item.get("atomicWrite") is True]
    tests = [item for item in typed if item.get("kind") == "focused-test"]
    rollbacks = [item for item in typed if item.get("kind") == "file-rollback"]
    noops = [item for item in typed if item.get("kind") == "local-action-verified-noop"]
    satisfaction_receipts = [
        item for item in typed if item.get("kind") == "local-action-source-satisfaction"
    ]
    normalization_receipts = [
        item for item in typed if item.get("kind") == "local-action-proposal-normalization"
    ]
    reconciliations = [
        item for item in typed if item.get("kind") == "local-action-file-reconciliation"
    ]

    if completed and applicable:
        if edits and not mutation_authorized:
            issues.append("mutation-receipt-without-authorization")
        if noops and not mutation_authorized:
            issues.append("verified-noop-receipt-without-mutation-authorization")
        if len(noops) > 1:
            issues.append("multiple-verified-noop-receipts")
        if len(satisfaction_receipts) > 1:
            issues.append("multiple-source-satisfaction-receipts")
        if len(normalization_receipts) > 1:
            issues.append("multiple-noop-normalization-receipts")
        if (satisfaction_receipts or normalization_receipts) and not noops:
            issues.append("noop-evidence-without-verified-noop")
        if noops and edits:
            issues.append("verified-noop-with-controller-edit")
        if noops and rollbacks:
            issues.append("verified-noop-with-rollback")
        if mutation_authorized:
            controller_resolutions = len(edits) + len(noops)
            if controller_resolutions != 1:
                issues.append(
                    "missing-controller-resolution-receipt"
                    if not controller_resolutions
                    else "multiple-controller-resolution-receipts"
                )
            if edits and rollbacks:
                issues.append("controller-edit-was-rolled-back")
            if atomic_edits and len(atomic_edits) != len(edits):
                issues.append("mixed-atomic-and-staged-controller-edits")
            expected_reconciliations = 0 if atomic_edits else 1
            if len(reconciliations) != expected_reconciliations:
                issues.append(
                    "unexpected-final-reconciliation"
                    if atomic_edits
                    else "missing-final-reconciliation"
                    if not reconciliations
                    else "multiple-final-reconciliations"
                )
        if noops:
            noop_test_run = noops[0].get("testRun") is True
            if noop_test_run and len(tests) != 1:
                issues.append("verified-noop-test-receipt-missing")
            elif not noop_test_run and tests:
                issues.append("verified-noop-test-flag-mismatch")
        elif test_authorized:
            if len(tests) != 1:
                issues.append(
                    "missing-focused-test-receipt"
                    if not tests
                    else "multiple-focused-test-receipts"
                )
        if tests and not test_authorized:
            issues.append("focused-test-receipt-without-authorization")
        if edits and reconciliations:
            edit_index = typed.index(edits[0])
            reconciliation_index = typed.index(reconciliations[-1])
            if edit_index >= reconciliation_index:
                issues.append("final-reconciliation-precedes-controller-edit")
            if tests and not (edit_index < typed.index(tests[0]) < reconciliation_index):
                issues.append("focused-test-receipt-out-of-order")
        if noops and reconciliations:
            noop_index = typed.index(noops[0])
            reconciliation_index = typed.index(reconciliations[-1])
            if noop_index >= reconciliation_index:
                issues.append("final-reconciliation-precedes-verified-noop")
            if tests and not (noop_index < typed.index(tests[0]) < reconciliation_index):
                issues.append("focused-test-receipt-out-of-order")
            for auxiliary in [*satisfaction_receipts, *normalization_receipts]:
                if typed.index(auxiliary) >= noop_index:
                    issues.append("noop-evidence-receipt-out-of-order")
            noop = noops[0]
            for satisfaction in satisfaction_receipts:
                if satisfaction.get("paths") != noop.get("paths"):
                    issues.append("source-satisfaction-noop-path-mismatch")
                if satisfaction.get("requestSha256") != noop.get("requestSha256"):
                    issues.append("source-satisfaction-noop-request-mismatch")
                if satisfaction.get("sourceSha256") != noop.get("sourceSha256"):
                    issues.append("source-satisfaction-noop-source-mismatch")
                if (
                    satisfaction.get("contextStart") != noop.get("contextStart")
                    or satisfaction.get("contextEnd") != noop.get("contextEnd")
                    or satisfaction.get("contextSha256") != noop.get("contextSha256")
                ):
                    issues.append("source-satisfaction-noop-context-mismatch")
            for normalization in normalization_receipts:
                if normalization.get("paths") != noop.get("paths"):
                    issues.append("noop-normalization-path-mismatch")
                if normalization.get("outputProposalSha256") != noop.get("proposalSha256"):
                    issues.append("noop-normalization-output-mismatch")

    issues = list(dict.fromkeys(issues))
    return {
        "kind": "local-action-completion-proof",
        "status": "pass" if not issues else "fail",
        "applicable": applicable,
        "mayClaimComplete": completed and applicable and not issues,
        "mutationAuthorized": mutation_authorized,
        "testAuthorized": test_authorized,
        "retainedMutation": bool(edits) and not rollbacks and not issues,
        "verifiedNoOp": bool(noops) and not issues,
        "receiptKinds": [item.get("kind") for item in typed],
        "receiptIds": [item.get("id") for item in typed],
        "issues": issues,
        "receipts": typed,
    }


def _normalize_command_receipts(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    receipts = []
    for index, candidate in enumerate(value, start=1):
        if not isinstance(candidate, Mapping):
            receipts.append(
                {
                    "id": f"command-{index}",
                    "command": "",
                    "status": "invalid",
                    "exitCode": None,
                    "verified": False,
                    "writeDetected": False,
                    "writeSignals": [],
                    "hasHeredoc": False,
                }
            )
            continue
        if _text(candidate.get("kind")).lower() in _LOCAL_ACTION_RECEIPT_KINDS:
            receipts.append(_normalize_typed_local_action_receipt(candidate, index))
            continue
        command = _text(candidate.get("command"))
        raw_exit_code = (
            candidate.get("exitCode")
            if candidate.get("exitCode") is not None
            else candidate.get("returnCode")
        )
        exit_code, exit_error = _return_code(raw_exit_code)
        status = _text(candidate.get("status")).lower()
        inspection = inspect_shell_command(command)
        receipts.append(
            {
                "id": _text(candidate.get("id")) or f"command-{index}",
                "command": command,
                "status": status,
                "exitCode": exit_code if raw_exit_code is not None else None,
                "verified": bool(
                    command
                    and raw_exit_code is not None
                    and not exit_error
                    and exit_code == 0
                    and status not in {"error", "fail", "failed", "timeout"}
                ),
                "writeDetected": bool(inspection.get("writeDetected")),
                "writeSignals": inspection.get("signals") or [],
                "hasHeredoc": bool(inspection.get("hasHeredoc")),
            }
        )
    return receipts


def _declares_read_only(*values: Any) -> bool:
    return any(
        "read-only" in _text(value).lower() or "read only" in _text(value).lower()
        for value in values
    )


def command_completion_contract(
    *,
    command_receipts: Any,
    semantic_receipt: Any,
    latest_user_intent: Any,
    access_level: Any,
    plan_access_level: Any = "",
    proof_requirements: Any = (),
    operation_plan: Any = None,
    completed: bool,
) -> Dict[str, Any]:
    """Require command success to prove the latest intent and respect access claims."""

    receipts = _normalize_command_receipts(command_receipts)
    semantic = _normalize_semantic_receipt(semantic_receipt)
    local_action_proof = local_action_completion_proof_contract(
        command_receipts,
        proof_requirements=proof_requirements,
        operation_plan=operation_plan,
        completed=completed,
    )
    latest = " ".join(_text(latest_user_intent).split())
    latest_digest = intent_digest(latest)
    issues = []
    mutation_detected = any(item.get("writeDetected") for item in receipts)
    read_only = _declares_read_only(access_level, plan_access_level)

    if read_only and mutation_detected:
        issues.append("read-only-command-writes")
    if local_action_proof.get("status") == "fail":
        issues.extend(local_action_proof.get("issues") or [])
    if completed and receipts:
        if any(not item.get("verified") for item in receipts):
            issues.append("unverified-command-receipt")
        if _CAPABILITY_QUERY_RE.search(latest):
            issues.append("command-executed-for-capability-query")
        if semantic.get("kind") != "semantic-completion":
            issues.append("missing-semantic-completion-receipt")
        elif not latest_digest:
            issues.append("missing-latest-intent-for-semantic-proof")
        elif semantic.get("intentDigest") != latest_digest:
            issues.append("stale-semantic-completion-receipt")
        elif not semantic.get("satisfied") or not semantic.get("summary"):
            issues.append("unsatisfied-semantic-completion-receipt")
        else:
            receipt_ids = {item.get("id") for item in receipts if item.get("id")}
            evidence_ids = set(semantic.get("evidenceReceiptIds") or [])
            if not receipt_ids.issubset(evidence_ids):
                issues.append("semantic-receipt-missing-command-evidence")

    return {
        "kind": "command-completion-contract",
        "status": "pass" if not issues else "fail",
        "issues": list(dict.fromkeys(issues)),
        "latestIntentDigest": latest_digest,
        "latestIntentKind": (
            "capability-query" if _CAPABILITY_QUERY_RE.search(latest) else "task"
        ),
        "readOnlyDeclared": read_only,
        "mutationDetected": mutation_detected,
        "commandReceipts": receipts,
        "semanticReceipt": semantic,
        "localActionProof": local_action_proof,
    }


def _normalize_handler_result(
    capability_plan: Mapping[str, Any],
    raw: Any,
    *,
    executor_name: str,
    handler_key: str,
    context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalize one executor result without trusting its completion claim."""

    if not isinstance(raw, Mapping):
        return {
            "eligible": True,
            "handled": False,
            "handlerKey": handler_key,
            "executor": executor_name,
            "mode": handler_key.replace("_", "-"),
            "engine": "local-knowledge",
            "accessLevel": "local-knowledge",
            "thought": "",
            "answer": "",
            "returnCode": 1,
            "normalize": False,
            "declaredOutcome": "invalid-result",
            "outcome": "failed",
            "outcomeAdjusted": True,
            "missing": [],
            "proofPolicy": _text(capability_plan.get("proof_policy")),
            "contractIssues": ["invalid-result-type"],
            "commandContract": {},
            "commandReceipts": [],
            "semanticReceipt": {},
            "templateOwnership": {},
            "sourceObservations": [],
            "error": "Capability handler must return a mapping result.",
        }

    answer = _text(raw.get("answer"))
    missing = _missing_items(raw.get("missing"))
    access_level = _text(raw.get("accessLevel")) or "local-knowledge"
    declared_outcome = _text(raw.get("outcome")).lower()
    requested_outcome = declared_outcome or ("completed" if answer else "unhandled")
    return_code, return_code_error = _return_code(raw.get("returnCode"))
    declared_error = _text(raw.get("error"))
    template_ownership = (
        dict(raw.get("templateOwnership"))
        if isinstance(raw.get("templateOwnership"), Mapping)
        else {}
    )
    source_observations, source_observation_issues = normalize_source_observations(
        raw.get("sourceObservations")
    )
    source_receipts = [
        dict(item)
        for item in (raw.get("sourceReceipts") or [])
        if isinstance(item, Mapping)
    ]
    active_context = context if isinstance(context, Mapping) else {}
    latest_intent = latest_user_intent_text(active_context.get("messages"))
    active_route = (
        active_context.get("route")
        if isinstance(active_context.get("route"), Mapping)
        else {}
    )
    active_frame = (
        active_context.get("intentFrame")
        if isinstance(active_context.get("intentFrame"), Mapping)
        else active_route.get("intentFrame")
        if isinstance(active_route.get("intentFrame"), Mapping)
        else {}
    )
    operation_plan = (
        active_frame.get("operationPlan")
        if isinstance(active_frame.get("operationPlan"), Mapping)
        else raw.get("operationPlan")
        if isinstance(raw.get("operationPlan"), Mapping)
        else {}
    )
    command_contract = command_completion_contract(
        command_receipts=raw.get("commandReceipts"),
        semantic_receipt=raw.get("semanticReceipt"),
        latest_user_intent=latest_intent,
        access_level=access_level,
        plan_access_level=capability_plan.get("access_level"),
        proof_requirements=capability_plan.get("proof_requirements"),
        operation_plan=operation_plan,
        completed=requested_outcome == "completed",
    )
    issues = []

    if return_code_error:
        issues.append("invalid-return-code")
    if return_code != 0:
        issues.append("nonzero-return-code")
    if declared_error:
        issues.append("declared-error")
    if requested_outcome not in EXECUTION_OUTCOMES:
        issues.append("invalid-outcome")
    if not answer:
        issues.append("missing-answer")
    if answer and requested_outcome == "completed" and missing:
        issues.append("completed-with-missing-requirements")
    issues.extend(command_contract.get("issues") or [])
    issues.extend(source_observation_issues)

    invalid_execution = bool(
        return_code_error
        or return_code != 0
        or declared_error
        or requested_outcome not in EXECUTION_OUTCOMES
        or command_contract.get("status") == "fail"
    )
    if invalid_execution:
        outcome = "failed"
        handled = False
    elif not answer:
        outcome = "unhandled"
        handled = False
    elif requested_outcome == "completed" and missing:
        outcome = "bounded"
        handled = True
    else:
        outcome = requested_outcome
        handled = outcome in HANDLED_OUTCOMES

    if outcome == "failed" and return_code == 0:
        return_code = 1
    error = declared_error or return_code_error
    if not error and "nonzero-return-code" in issues:
        error = f"Capability handler returned nonzero code {return_code}."
    if not error and "invalid-outcome" in issues:
        error = f"Unsupported capability outcome `{requested_outcome}`."
    if not error and requested_outcome == "failed":
        error = "Capability handler declared a failed outcome."
    if not error and "read-only-command-writes" in issues:
        error = "Capability declared read-only access, but its command receipt contains a filesystem write signal."
    if not error and "command-executed-for-capability-query" in issues:
        error = "Command execution cannot satisfy the latest turn because it asks about capability rather than requesting execution."
    if not error and "missing-semantic-completion-receipt" in issues:
        error = "A zero exit code does not prove completion without a semantic receipt bound to the latest user intent."
    if not error and "stale-semantic-completion-receipt" in issues:
        error = "The semantic completion receipt belongs to an earlier user intent."
    if not error and command_contract.get("localActionProof", {}).get("status") == "fail":
        error = "Local-action completion lacks a retained, ordered controller proof chain."
    if not error and command_contract.get("status") == "fail":
        error = "Command-backed completion did not satisfy the typed execution contract."

    return {
        "eligible": True,
        "handled": handled,
        "handlerKey": handler_key,
        "executor": executor_name,
        "mode": _text(raw.get("mode")) or handler_key.replace("_", "-"),
        "engine": _text(raw.get("engine")) or "local-knowledge",
        "accessLevel": access_level,
        "thought": _text(raw.get("thought")),
        "answer": answer,
        "returnCode": return_code,
        "normalize": bool(raw.get("normalize", False)),
        "textLocked": bool(raw.get("textLocked", False)),
        "declaredOutcome": requested_outcome,
        "outcome": outcome,
        "outcomeAdjusted": outcome != requested_outcome,
        "missing": missing,
        "proofPolicy": _text(capability_plan.get("proof_policy")),
        "contractIssues": issues,
        "commandContract": command_contract,
        "localActionProof": command_contract.get("localActionProof") or {},
        "commandReceipts": command_contract.get("commandReceipts") or [],
        "semanticReceipt": command_contract.get("semanticReceipt") or {},
        "templateOwnership": template_ownership,
        "sourceObservations": source_observations,
        "sourceReceipts": source_receipts,
        "error": error,
    }


def synthetic_execution_contract_check() -> Dict[str, Any]:
    """Exercise the honest-completion invariants used by executor health."""

    plan = {"proof_policy": "verified result or exact blocker"}

    def normalize(raw: Any, messages: Any = None) -> Dict[str, Any]:
        return _normalize_handler_result(
            plan,
            raw,
            executor_name="synthetic",
            handler_key="contract_probe",
            context={"messages": messages or []},
        )

    completed = normalize({"answer": "Verified result.", "returnCode": 0})
    nonzero = normalize(
        {"answer": "Completed successfully.", "returnCode": 2, "outcome": "completed"}
    )
    incomplete = normalize(
        {
            "answer": "Completed successfully.",
            "returnCode": 0,
            "outcome": "completed",
            "missing": ["verification receipt"],
        }
    )
    invalid_outcome = normalize(
        {"answer": "Completed successfully.", "outcome": "definitely-done"}
    )
    invalid_code = normalize({"answer": "Completed successfully.", "returnCode": "two"})
    fractional_code = normalize({"answer": "Completed successfully.", "returnCode": 0.5})
    explicit_error = normalize(
        {"answer": "Completed successfully.", "returnCode": 0, "error": "tool failed"}
    )
    string_missing = normalize(
        {"answer": "Need one receipt.", "outcome": "needs-input", "missing": "receipt"}
    )
    typed_template_ownership = normalize(
        {
            "answer": "A bounded specialist answer.",
            "templateOwnership": {
                "kind": "template-ownership",
                "receiptId": "owner-1",
                "ownerDomain": "synthetic-specialist",
            },
        }
    )
    empty = normalize({})
    task_messages = [{"role": "user", "text": "Count the lines in input.txt."}]
    task_semantic = build_semantic_completion_receipt(
        task_messages,
        "Counted the requested file.",
        ["cmd-1"],
    )
    safe_command = {
        "answer": "input.txt has 12 lines.",
        "outcome": "completed",
        "returnCode": 0,
        "commandReceipts": [
            {"id": "cmd-1", "command": "wc -l input.txt", "status": "pass", "exitCode": 0}
        ],
        "semanticReceipt": task_semantic,
    }
    matching_semantic = normalize(safe_command, task_messages)
    zero_exit_only = normalize(
        {key: value for key, value in safe_command.items() if key != "semanticReceipt"},
        task_messages,
    )
    stale_semantic = normalize(
        {
            **safe_command,
            "semanticReceipt": build_semantic_completion_receipt(
                [{"role": "user", "text": "Count a different file."}],
                "Counted a file.",
                ["cmd-1"],
            ),
        },
        task_messages,
    )
    read_only_write = normalize(
        {
            "answer": "Created output.txt.",
            "outcome": "completed",
            "returnCode": 0,
            "accessLevel": "read-only-local-files",
            "commandReceipts": [
                {
                    "id": "cmd-1",
                    "command": "/bin/bash -lc \"cat > output.txt <<'EOF'\\nresult\\nEOF\"",
                    "status": "pass",
                    "exitCode": 0,
                }
            ],
            "semanticReceipt": build_semantic_completion_receipt(
                task_messages,
                "Created output.txt.",
                ["cmd-1"],
            ),
        },
        task_messages,
    )
    capability_messages = [
        {
            "role": "user",
            "text": "When I say could you, I mean do you have the capability.",
        }
    ]
    capability_query_execution = normalize(
        {
            **safe_command,
            "semanticReceipt": build_semantic_completion_receipt(
                capability_messages,
                "Executed a command.",
                ["cmd-1"],
            ),
        },
        capability_messages,
    )
    local_plan = {
        "proof_policy": "verified controller edit or explicit no-op, plus focused test when run and reconciliation",
        "proof_requirements": [
            "controller-edit-if-mutation-authorized",
            "verified-noop-alternative-controller-resolution",
            "focused-test-if-test-authorized",
            "verified-final-reconciliation",
            "rollback-precludes-completion",
        ],
    }
    local_messages = [{"role": "user", "text": "Update the local panel and test it."}]
    local_context = {
        "messages": local_messages,
        "intentFrame": {
            "operationPlan": {
                "allowedNow": ["inspect", "edit", "test"],
                "readOnly": False,
            }
        },
    }
    local_edit = {
        "id": "edit-1",
        "kind": "file-change",
        "status": "completed",
        "verified": True,
        "exitCode": 0,
        "paths": ["module.py"],
        "beforeSha256": "1" * 64,
        "afterSha256": "2" * 64,
        "mutationMarkers": ["controller-owned-edit"],
    }
    local_test = {
        "id": "test-1",
        "kind": "focused-test",
        "status": "passed",
        "verified": True,
        "exitCode": 0,
        "paths": ["tools/focused_smoke.py"],
        "mutationMarkers": [],
    }
    local_reconciliation = {
        "id": "reconcile-1",
        "kind": "local-action-file-reconciliation",
        "status": "verified",
        "verified": True,
        "exitCode": 0,
        "changedPaths": [],
        "mutationMarkers": [],
    }
    local_receipts = [local_edit, local_test, local_reconciliation]
    local_semantic = build_semantic_completion_receipt(
        local_messages,
        "Retained the controller edit after its focused test and reconciliation.",
        ["edit-1", "test-1", "reconcile-1"],
    )
    local_valid = _normalize_handler_result(
        local_plan,
        {
            "answer": "The local change completed with focused verification.",
            "outcome": "completed",
            "returnCode": 0,
            "commandReceipts": local_receipts,
            "semanticReceipt": local_semantic,
        },
        executor_name="local-agent",
        handler_key="local_product_action",
        context=local_context,
    )
    local_rollback = {
        "id": "rollback-1",
        "kind": "file-rollback",
        "status": "completed",
        "verified": True,
        "exitCode": 0,
        "paths": ["module.py"],
        "afterSha256": "1" * 64,
        "restoredSha256": "1" * 64,
        "mutationMarkers": ["controller-owned-rollback"],
    }
    local_rolled_back = _normalize_handler_result(
        local_plan,
        {
            "answer": "The attempted change was rolled back.",
            "outcome": "completed",
            "returnCode": 0,
            "commandReceipts": [local_edit, local_test, local_rollback, local_reconciliation],
            "semanticReceipt": build_semantic_completion_receipt(
                local_messages,
                "The controller sequence ended after rollback.",
                ["edit-1", "test-1", "rollback-1", "reconcile-1"],
            ),
        },
        executor_name="local-agent",
        handler_key="local_product_action",
        context=local_context,
    )
    local_noop = {
        "id": "noop-1",
        "kind": "local-action-verified-noop",
        "status": "verified",
        "verified": True,
        "exitCode": 0,
        "result": "requested-state-already-satisfied",
        "paths": ["module.py"],
        "changedPaths": [],
        "requestSha256": "3" * 64,
        "sourceSha256": "1" * 64,
        "contextStart": 10,
        "contextEnd": 30,
        "contextSha256": "4" * 64,
        "proposalSha256": "5" * 64,
        "testRequested": True,
        "testRun": False,
        "sourceEvidenceVerified": True,
        "controllerOwned": True,
        "sourceContentsRecorded": False,
        "proposalContentsRecorded": False,
        "mutationMarkers": [],
    }
    local_satisfaction = {
        "id": "satisfaction-1",
        "kind": "local-action-source-satisfaction",
        "status": "verified",
        "verified": True,
        "verdict": "satisfied",
        "path": "module.py",
        "requestSha256": "3" * 64,
        "typedRequestSha256": "6" * 64,
        "sourceSha256": "1" * 64,
        "contextStart": 10,
        "contextEnd": 30,
        "contextSha256": "4" * 64,
        "verdictSha256": "7" * 64,
        "controllerBound": True,
        "verdictContentsRecorded": False,
    }
    local_noop_receipts = [local_satisfaction, local_noop, local_reconciliation]
    local_verified_noop = _normalize_handler_result(
        local_plan,
        {
            "answer": "The requested behavior was already present and controller-verified.",
            "outcome": "completed",
            "returnCode": 0,
            "commandReceipts": local_noop_receipts,
            "semanticReceipt": build_semantic_completion_receipt(
                local_messages,
                "The controller verified the requested state without changing source.",
                ["satisfaction-1", "noop-1", "reconcile-1"],
            ),
        },
        executor_name="local-agent",
        handler_key="local_product_action",
        context=local_context,
    )
    checks = {
        "verifiedCompletionPasses": bool(
            completed.get("handled")
            and completed.get("outcome") == "completed"
            and completed.get("returnCode") == 0
        ),
        "nonzeroFailsClosed": bool(
            not nonzero.get("handled")
            and nonzero.get("outcome") == "failed"
            and "nonzero-return-code" in (nonzero.get("contractIssues") or [])
        ),
        "missingProofDowngradesToBounded": bool(
            incomplete.get("handled")
            and incomplete.get("outcome") == "bounded"
            and incomplete.get("outcomeAdjusted")
        ),
        "unknownOutcomeFailsClosed": bool(
            not invalid_outcome.get("handled")
            and invalid_outcome.get("outcome") == "failed"
            and "invalid-outcome" in (invalid_outcome.get("contractIssues") or [])
        ),
        "invalidReturnCodeFailsClosed": bool(
            not invalid_code.get("handled")
            and invalid_code.get("outcome") == "failed"
            and invalid_code.get("returnCode") == 1
        ),
        "fractionalReturnCodeFailsClosed": bool(
            not fractional_code.get("handled")
            and fractional_code.get("outcome") == "failed"
            and fractional_code.get("returnCode") == 1
        ),
        "declaredErrorFailsClosed": bool(
            not explicit_error.get("handled")
            and explicit_error.get("outcome") == "failed"
            and explicit_error.get("error") == "tool failed"
        ),
        "scalarMissingIsOneRequirement": string_missing.get("missing") == ["receipt"],
        "emptyResultIsUnhandled": bool(
            not empty.get("handled") and empty.get("outcome") == "unhandled"
        ),
        "proofPolicyPropagates": completed.get("proofPolicy") == plan["proof_policy"],
        "typedTemplateOwnershipPropagates": bool(
            typed_template_ownership.get("templateOwnership", {}).get("kind")
            == "template-ownership"
            and typed_template_ownership.get("templateOwnership", {}).get("receiptId")
            == "owner-1"
        ),
        "matchingSemanticCommandPasses": bool(
            matching_semantic.get("handled")
            and matching_semantic.get("outcome") == "completed"
        ),
        "zeroExitNeedsSemanticProof": bool(
            not zero_exit_only.get("handled")
            and zero_exit_only.get("outcome") == "failed"
            and "missing-semantic-completion-receipt"
            in (zero_exit_only.get("contractIssues") or [])
        ),
        "staleIntentReceiptFails": bool(
            not stale_semantic.get("handled")
            and "stale-semantic-completion-receipt"
            in (stale_semantic.get("contractIssues") or [])
        ),
        "readOnlyWriteFails": bool(
            not read_only_write.get("handled")
            and "read-only-command-writes"
            in (read_only_write.get("contractIssues") or [])
        ),
        "capabilityQueryDoesNotExecute": bool(
            not capability_query_execution.get("handled")
            and "command-executed-for-capability-query"
            in (capability_query_execution.get("contractIssues") or [])
        ),
        "typedLocalActionProofCompletes": bool(
            local_valid.get("handled")
            and local_valid.get("outcome") == "completed"
            and local_valid.get("localActionProof", {}).get("retainedMutation") is True
        ),
        "typedLocalActionRollbackFailsClosed": bool(
            not local_rolled_back.get("handled")
            and local_rolled_back.get("outcome") == "failed"
            and "controller-edit-was-rolled-back"
            in (local_rolled_back.get("contractIssues") or [])
        ),
        "typedLocalActionVerifiedNoOpCompletes": bool(
            local_verified_noop.get("handled")
            and local_verified_noop.get("outcome") == "completed"
            and local_verified_noop.get("localActionProof", {}).get("verifiedNoOp") is True
            and local_verified_noop.get("localActionProof", {}).get("retainedMutation") is False
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "failures": failures,
    }


class CapabilityExecutorRouter:
    """Bind each migrated handler key to exactly one callable executor."""

    def __init__(
        self,
        bindings: Iterable[Tuple[str, CapabilityHandler]],
        *,
        executor_name: str = "deterministic",
    ):
        self.executor_name = _text(executor_name) or "deterministic"
        self._bindings: Dict[str, CapabilityHandler] = {}
        self._duplicates = []
        for handler_key, handler in bindings:
            key = _text(handler_key)
            if not key or not callable(handler):
                continue
            if key in self._bindings:
                self._duplicates.append(key)
                continue
            self._bindings[key] = handler

    @property
    def handler_keys(self) -> Tuple[str, ...]:
        return tuple(sorted(self._bindings))

    def health(self, expected_handler_keys: Sequence[str]) -> Dict[str, Any]:
        expected = {_text(key) for key in expected_handler_keys if _text(key)}
        actual = set(self._bindings)
        missing = sorted(expected.difference(actual))
        extra = sorted(actual.difference(expected))
        duplicates = sorted(set(self._duplicates))
        result_contract = synthetic_execution_contract_check()
        return {
            "status": (
                "pass"
                if not missing
                and not extra
                and not duplicates
                and result_contract.get("status") == "pass"
                else "fail"
            ),
            "expected": sorted(expected),
            "bound": sorted(actual),
            "missing": missing,
            "extra": extra,
            "duplicates": duplicates,
            "resultContract": result_contract,
        }

    def execute(
        self,
        capability_plan: Optional[Dict[str, Any]],
        context: CapabilityContext,
    ) -> Dict[str, Any]:
        plan = capability_plan if isinstance(capability_plan, dict) else {}
        if (
            not plan.get("registered")
            or _text(plan.get("executor")) != self.executor_name
            or _text(plan.get("execution_binding")) != "router"
        ):
            return {
                "eligible": False,
                "handled": False,
                "handlerKey": _text(plan.get("handler_key")),
                "executor": self.executor_name,
                "reason": f"capability is not router-bound to the {self.executor_name} executor",
            }
        handler_key = _text(plan.get("handler_key"))
        handler = self._bindings.get(handler_key)
        if handler is None:
            return _normalize_handler_result(
                plan,
                {
                    "outcome": "failed",
                    "returnCode": 1,
                    "error": f"No {self.executor_name} executor is bound for `{handler_key}`.",
                },
                executor_name=self.executor_name,
                handler_key=handler_key,
                context=context,
            )
        try:
            raw = handler(context) or {}
        except Exception as exc:
            return _normalize_handler_result(
                plan,
                {
                    "outcome": "failed",
                    "returnCode": 1,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                executor_name=self.executor_name,
                handler_key=handler_key,
                context=context,
            )
        return _normalize_handler_result(
            plan,
            raw,
            executor_name=self.executor_name,
            handler_key=handler_key,
            context=context,
        )
