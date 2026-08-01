"""Structured answer state for the Codex CLI UI response pipeline."""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ENVELOPE_VERSION = 1
FINAL_STATES = {"complete", "blocked"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def text_sha256(value: Any) -> str:
    return hashlib.sha256(_text(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AnswerRevision:
    stage: str
    source_sha256: str
    result_sha256: str
    reason: str = ""


@dataclass(frozen=True)
class AnswerEnvelope:
    objective: str
    text: str
    status: str = "draft"
    stage: str = "primary-worker"
    evidence: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    provenance: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    artifacts: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    gaps: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    revisions: Tuple[AnswerRevision, ...] = field(default_factory=tuple)
    final_text_sha256: str = ""
    created_at: float = field(default_factory=time.time)
    version: int = ENVELOPE_VERSION

    @classmethod
    def from_text(cls, text: Any, objective: Any = "") -> "AnswerEnvelope":
        return cls(objective=_text(objective), text=_text(text))

    def revise(
        self,
        text: Any,
        stage: str,
        reason: str = "",
        gaps: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> "AnswerEnvelope":
        if self.status in FINAL_STATES:
            raise ValueError("Final answer envelopes are immutable.")
        next_text = _text(text)
        revision = AnswerRevision(
            stage=_text(stage) or "revision",
            source_sha256=text_sha256(self.text),
            result_sha256=text_sha256(next_text),
            reason=_text(reason),
        )
        return replace(
            self,
            text=next_text,
            stage=revision.stage,
            gaps=tuple(gaps or ()),
            revisions=self.revisions + (revision,),
        )

    def with_evidence(self, evidence: Optional[Iterable[Dict[str, Any]]]) -> "AnswerEnvelope":
        if self.status in FINAL_STATES:
            raise ValueError("Final answer envelopes are immutable.")
        return replace(self, evidence=tuple(item for item in (evidence or ()) if isinstance(item, dict)))

    def with_provenance(self, provenance: Optional[Iterable[Dict[str, Any]]]) -> "AnswerEnvelope":
        if self.status in FINAL_STATES:
            raise ValueError("Final answer envelopes are immutable.")
        return replace(self, provenance=tuple(item for item in (provenance or ()) if isinstance(item, dict)))

    def finalize(self, status: str, stage: str = "final-gate") -> "AnswerEnvelope":
        normalized = _text(status).lower()
        if normalized not in FINAL_STATES:
            raise ValueError("Answer envelope status must be complete or blocked.")
        return replace(
            self,
            status=normalized,
            stage=_text(stage) or "final-gate",
            final_text_sha256=text_sha256(self.text),
        )

    def verify_final_integrity(self, text: Any) -> bool:
        if self.status not in FINAL_STATES or not self.final_text_sha256:
            return False
        return self.final_text_sha256 == text_sha256(text)

    def public_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["created_at"] = round(float(self.created_at), 3)
        return value


def synthetic_envelope_check() -> Dict[str, Any]:
    base = AnswerEnvelope.from_text("Draft answer", objective="Compare A and B")
    revised = base.revise("Qualified answer", "analytical-repair", reason="removed unsupported claim").with_provenance(
        [
            {
                "kind": "technical-claim-audit",
                "verdict": "bounded",
                "unsupportedCount": 1,
                "cacheHit": False,
            }
        ]
    )
    final = revised.finalize("complete")
    mutation_blocked = False
    try:
        final.revise("Changed after final", "late-guard")
    except ValueError:
        mutation_blocked = True
    ok = (
        base.status == "draft"
        and len(revised.revisions) == 1
        and len(revised.provenance) == 1
        and revised.provenance[0].get("kind") == "technical-claim-audit"
        and final.verify_final_integrity("Qualified answer")
        and not final.verify_final_integrity("Changed after final")
        and mutation_blocked
    )
    return {
        "status": "pass" if ok else "fail",
        "revisionCount": len(revised.revisions),
        "provenanceCount": len(revised.provenance),
        "finalIntegrity": final.verify_final_integrity("Qualified answer"),
        "mutationBlocked": mutation_blocked,
    }
