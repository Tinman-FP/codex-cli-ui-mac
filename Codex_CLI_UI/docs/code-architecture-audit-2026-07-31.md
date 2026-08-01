# Codex CLI UI Architecture Audit

Updated: 2026-08-01

## Bottom line

Codex CLI UI now has the right architectural spine for a capable local assistant: a generic intelligence kernel interprets the complete turn, a typed capability registry selects one execution contract, and a structured answer envelope preserves provenance and final-answer integrity. Migrated model-first lanes no longer pass through the old direct-answer lattice, and engineering/calculation/source-backed answers now have distinct review policies instead of sharing a broad rewrite chain.

The product is materially better, but the migration is not finished. `server.py` remains a compatibility monolith containing hundreds of legacy classifiers and more than a thousand direct-answer helpers. Those paths are bounded behind capability authority for migrated intents, but they still raise change risk and slow future development. The next architectural phase should extract capabilities and delete superseded legacy code, not add more keyword patches.

## Measured state

- `server.py`: 134,634 lines, 4,087 top-level functions.
- Legacy classifier surface: 956 top-level `is_*_question` functions.
- Direct-answer surface: 1,255 top-level function names containing `direct_answer`.
- `route_manager`: 5,790 lines.
- `task_contract`: 6,694 lines.
- `package_health_report`: 10,412 lines.
- `intelligence_kernel.py`: 1,310 lines.
- `capability_registry.py`: 368 lines, 17 registered capability contracts.
- `answer_envelope.py`: 139 lines with immutable-final integrity checks.
- Browser client: `app.js` 5,891 lines; `styles.css` 3,783 lines; `index.html` 542 lines.

## Implemented architecture

### 1. One intent owner before execution

The intelligence kernel builds a structured turn frame from the entire recent conversation, including the objective, objects, constraints, requested action, evidence need, missing information, and forbidden routes. Its decision selects model-first, capability-first, or deterministic execution before old direct-answer handlers are considered.

Registered intents now carry a typed `capabilityPlan` with an executor, handler key, access level, proof policy, review policy, and version. A migrated capability is allowed one executor; unrelated legacy handlers cannot seize the turn from an isolated keyword.

### 2. Review policy belongs to the capability

The registry separates review by failure mode:

- General conversation and comparison: adversarial reasoning audit.
- Engineering power conversion: deterministic calculation contract.
- Engineering advisory: deterministic engineering, evidence, task, and final-envelope contract.
- Source-backed answers: source-fidelity audit.
- Local file/action capabilities: artifact and proof contracts.

This removed the previous pattern in which manager review, analytical coaching, research recovery, and final polish could all rewrite the same answer. In particular, engineering advisory now preserves the primary reasoning unless a concrete invariant or evidence boundary fails; it never launches the legacy Quality Coach as a second author.

### 3. Clarification is a valid result

A question does not have to force an immediate answer. The final gate recognizes one focused question when a missing fact can reverse the recommendation or make an action unsafe. That clarification passes as the completed conversational outcome and is not rewritten into a refusal or a guessed recommendation.

### 4. Evidence boundaries are deterministic where possible

Unchecked product variants are generalized to the component class the user actually named. Uncited technical precision is removed, including numeric metric tables and Unicode-hyphenated ranges. High-confidence class-level physical inversions, such as claiming a desktop discrete-GPU system uses less power than an edge AI SoC, are corrected without another model pass.

Current, scientific, and document-specific questions still require evidence retrieval and source-bounded synthesis. The answer envelope records route, capability, evidence, review, and revision provenance before rendering.

### 5. Stream reliability and abandoned-run cleanup

`/api/run` emits silent heartbeat events during long local generations so browser and test clients do not mistake thinking time for a dead connection. If the client disconnects, the server now terminates the underlying Codex subprocess instead of leaving an invisible model job consuming memory and delaying the next turn.

## Remaining risks

### Monolithic compatibility surface - high

Typed authority prevents many precedence failures, but it does not make the 132,607-line server easy to maintain. The registry should become a package-level dispatcher, and each migrated capability should move to its own module with request, executor, verifier, and renderer types. Delete the corresponding legacy detector/answer family after adversarial and package-health coverage exists.

### Local model ceiling - high

The installed local models can still hallucinate product specifications, choose poor assumptions, or take 40-120 seconds on difficult turns. Prompting alone did not solve this: `qwen3.6:27b` was slower and more overconfident than `gpt-oss-20b` on the printer-camera architecture benchmark. The practical design is therefore one strong primary pass plus deterministic contracts and focused evidence retrieval, not cascades of local model rewrites.

### Claim structure is still partly inferred from prose - medium/high

The answer envelope is implemented, but many legacy checks still recover claims from rendered text with regular expressions. Future capability executors should return structured claims, assumptions, estimates, citations, and artifacts directly. The renderer should then be the only component that creates prose.

### Feedback promotion needs more longitudinal proof - medium

The feedback ledger stores redacted objective mismatch, correction class, repair strategy, and verification outcome. Promotion should remain conservative: only stable lessons that succeed on novel prompts and follow-ups should affect future routing. Never promote answer snippets or product-specific prose as general intelligence.

## Next migration slice

1. Split the registry, kernel, envelope, evidence retrieval, and supervisor into an `intelligence/` package with typed request/response boundaries.
2. Extract the highest-use capabilities from `server.py`: local file evidence, current web research, engineering advisory, source-backed reasoning, and Klipper migration.
3. Add structured claim objects to those executors and remove their prose-regex checks.
4. Delete each superseded legacy detector/direct-answer family after route coverage, adversarial conversation, and package-health tests pass.
5. Profile prompt evaluation and local inference separately; keep response latency visible in provenance and package health.

## Verification receipts

- Typed capability/answer architecture smoke: `/tmp/capability-answer-architecture-final.json`.
- Camera-server adversarial conversation: `data/golden_batch_results/adversarial-understanding/20260801T145738Z/adversarial-understanding-results.json`.
- Power-conversion adversarial conversations: `data/golden_batch_results/adversarial-understanding/20260801T121548Z/` and `20260801T121606Z/`.
- Generic reasoning decision audit: `/tmp/live-probability-decision-audit.json`.
- Final package-health, export, privacy, and handoff receipts are recorded in the latest `data/work_checkpoints/` checkpoint.
