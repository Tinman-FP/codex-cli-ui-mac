# Codex CLI UI Intelligence And Routing Research Plan

Date: 2026-07-17
Owner: Tinman / Codex CLI UI
Status: Research brief and rebuild plan

## Executive Conclusion

The current problem is not one bad route, one missing regex, or one weak personality prompt. The core failure is architectural: the app routes too early from keywords and special cases, then answers from a large direct-answer lattice. That can pass many regression tests while still failing the human task, because the system does not first create a durable, inspectable representation of what Tinman is actually asking.

The rebuild target should be:

1. Understand first.
2. Clarify when the objective or referent is uncertain.
3. Route from an explicit intent frame, not raw keywords.
4. Use tools and evidence only after the task contract is known.
5. Compose the final answer in a consistent, personable subject-matter-expert voice.
6. Learn from feedback by saving corrected intent frames, routing decisions, failure modes, and regression tests, not by copying canned answer text.

The practical architecture is a "strangler" rebuild: wrap the current monolith with a new intelligence kernel, move traffic through the kernel first, and gradually retire brittle direct-answer branches as new capability modules replace them. A full rewrite is possible, but doing it all at once would throw away useful local knowledge and create new failure modes. The right move is to replace the brain stem first.

## Local Diagnosis

Local inspection on 2026-07-17 found:

- `server.py` is about 110,257 lines.
- `tools/live_feedback_smoke.py` is about 8,255 lines.
- The codebase contains roughly 1,246 `*_direct_answer` functions.
- The codebase contains roughly 1,416 `is_*_question/request/followup/context` detectors.
- The live smoke harness contains roughly 207 explicit case IDs.

These numbers are not inherently bad. They show that a lot of knowledge and regression work exists. The failure is that this knowledge is organized as detector/template accretion instead of a smaller shared understanding model.

The Bambu H2D failure is a clean example:

User request:

> in the model health for the bambu h2d it is now showing printing, which is good, but i als want it to display percent complete and time remaining on the print.

The correct understanding is:

- Target surface: Codex CLI UI Model Health panel.
- Object: Bambu H2D.
- Current state: it shows printing.
- Requested change: display percent complete and time remaining.
- Needed evidence: whether the Bambu status source exposes progress and ETA.
- Correct action: inspect/update the Model Health status pipeline, or ask whether a temporary manual override is acceptable if live telemetry is not wired.
- Forbidden route: CAD/Fusion/geometry.

The observed behavior routed to CAD missing geometry. That means the system recognized the wrong task family before it understood the requested product surface.

## External Research Synthesis

### Human-AI Interaction

Microsoft's Guidelines for Human-AI Interaction are directly relevant. They emphasize making system capabilities clear, showing contextually relevant information, supporting efficient correction, scoping services when uncertain, explaining why the system behaved as it did, remembering recent interactions, learning from behavior, and notifying users about changes. The most important guideline for this failure class is "scope services when in doubt": if the system is uncertain about the user's goal, it should disambiguate or gracefully degrade instead of confidently pursuing the wrong task.

Source: https://www.microsoft.com/en-us/research/wp-content/uploads/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf

Google PAIR's mental-model guidance also fits: user frustration rises when the user's mental model of what the product can do diverges from what it actually does. Tinman expects a capable local teammate that understands app, printer, CAD, research, and project context. The app currently presents itself like that, but internally behaves like a pile of narrow detectors.

Sources:

- https://pair.withgoogle.com/chapter/mental-models/
- https://pair.withgoogle.com/guidebook/

NIST AI RMF adds the governance lens: roles, responsibilities, monitoring, transparency, and feedback mechanisms need to be part of the lifecycle, not afterthoughts. For this product, that means every self-improvement event should be traceable: original prompt, inferred intent frame, route, tools, answer, user feedback, corrected frame, regression added, and package-health result.

Sources:

- https://www.nist.gov/itl/ai-risk-management-framework
- https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf

NASA's human-autonomy work is useful because this app is not just a chatbot. It touches local files, machines, printers, CAD workflows, and live status. NASA frames trust calibration around mental models, transparency, and adaptive behavior. For Codex CLI UI, trust should be calibrated by making the app clear about what it knows, what it inferred, what it checked, and when it needs Tinman's decision.

Source: https://ntrs.nasa.gov/api/citations/20205003378/downloads/NASA-TM-20205003378.pdf

### Dialogue Management And Clarification

Rasa CALM is the most directly applicable system pattern. Rasa separates fluent LLM conversation from deterministic business logic. Its dialogue understanding component reads the conversation, creates structured commands, then a dialogue manager executes only designed workflows. That is very close to what Codex CLI UI needs: an LLM can infer "Tinman is asking to modify the Model Health panel", but deterministic code should decide which capability can perform that modification.

Sources:

- https://rasa.com/docs/learn/concepts/dialogue-understanding/
- https://rasa.com/docs/learn/concepts/calm/
- https://arxiv.org/pdf/2402.12234

Research on task-oriented dialogue also supports splitting each turn into domain detection/state tracking, database or tool lookup, and response generation. This is better than a single prompt or route classifier because the system can inspect the intermediate state before acting.

Source: https://aclanthology.org/2023.sigdial-1.21.pdf

Clarification research points in the same direction: useful assistants should ask clarifying questions when ambiguity changes the correct answer. The goal is not to ask more questions; it is to ask when answering would silently choose a risky interpretation.

Sources:

- https://arxiv.org/html/2410.13788v2
- https://www.microsoft.com/en-us/research/wp-content/uploads/2016/11/mixedinit.pdf
- https://acs.ist.psu.edu/misc/dirk-files/Papers/HRI-papers/User%20interface%20design%20issues/Principles%20of%20Mixed-Initiative%20User%20Interfaces..pdf

### Agent Orchestration

OpenAI's Agents documentation recommends making a clear choice between handoffs and "agents as tools." For Codex CLI UI, the better primary pattern is a manager-style workflow: one outer agent owns the conversation and calls bounded specialists as tools. Specialists should be added only when the contract changes materially, such as code editing, local evidence retrieval, CAD generation, machine status, current web research, or safety-sensitive actions.

Sources:

- https://developers.openai.com/api/docs/guides/agents/orchestration
- https://openai.github.io/openai-agents-python/handoffs/
- https://openai.github.io/openai-agents-python/guardrails/

OpenAI also stresses trace grading for agent workflows. This is crucial: final-answer grading alone misses the actual failure. We need to grade the trace:

- Did it build the right intent frame?
- Did it ask clarification when needed?
- Did it veto wrong routes?
- Did it call the correct capability?
- Did it verify evidence before claiming a result?
- Did the final answer sound like Tinman's teammate rather than a form letter?

Source: https://developers.openai.com/api/docs/guides/agent-evals

LangGraph's public docs reinforce the same engineering pattern: stateful graphs, persistence, human-in-the-loop checkpoints, retries, and errors as part of the flow. We do not need to install LangGraph immediately, but the design pattern is right.

Sources:

- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph
- https://docs.langchain.com/oss/python/langchain/human-in-the-loop

DSPy is relevant because it argues for programming language-model systems as structured modules rather than hand-tuning giant prompts. The useful lesson is not "install DSPy now"; it is that Codex CLI UI should have typed signatures for intent extraction, routing, evidence review, and response composition.

Sources:

- https://dspy.ai/
- https://hai.stanford.edu/research/dspy-compiling-declarative-language-model-calls-into-state-of-the-art-pipelines

### Conversation And Personality

Personality cannot be a wrapper over bad understanding. If the system misunderstands the task, warmer wording only makes the wrong answer more frustrating.

The target persona should be explicit and testable:

- Educated, practical, and direct.
- Conversational, not corporate.
- Comfortable asking one sharp question when that is the correct next move.
- Capable of saying "I do not know yet; I am going to check the right source."
- Varied in phrasing, without random fluff.
- Domain-adaptive: engineering questions get engineering judgment; product bugs get product-owner clarity; casual questions get warmth.

Google's conversation-design guidance maps well: move the conversation forward, be brief and relevant, use plain English, keep context, and vary frequent prompts so the assistant does not sound robotic.

Sources:

- https://developers.google.com/assistant/conversation-design/learn-about-conversation
- https://developers.google.com/assistant/conversation-design/create-a-persona

NN/g's chatbot research also matters: users prefer honesty over wrong answers, get annoyed by repeated canned responses, and need clear expectations about what the bot can do. For Tinman's product, the app should admit uncertainty and ask for missing context rather than reciting unrelated boilerplate.

Sources:

- https://www.nngroup.com/articles/chatbots/
- https://www.nngroup.com/articles/ai-chatbots-design-guidelines/

## Target Architecture

### 1. Intelligence Kernel

Add a new top-level module before the legacy route manager:

`intelligence_kernel.py`

Responsibilities:

- Assemble turn context.
- Extract an intent frame.
- Decide whether to clarify, answer, act, research, inspect local files, or route to a capability.
- Apply route vetoes.
- Produce a task contract.
- Pass work to existing tools or legacy handlers only after the task is understood.
- Save trace events.

This is the new front door. The old `route_manager()` becomes a fallback capability, not the source of truth.

### 2. Intent Frame Schema

Every turn should produce an intent frame before routing:

```json
{
  "user_goal": "Display print progress percentage and time remaining for the Bambu H2D in Model Health.",
  "target_surface": "codex_cli_ui.model_health",
  "domain": "local_app_product_bug",
  "object_refs": [
    {
      "name": "Bambu H2D",
      "type": "printer"
    }
  ],
  "current_state": "Panel already shows printing.",
  "requested_change": "Add percent complete and time remaining.",
  "action_type": "modify_app_behavior",
  "expected_output": "Code change or blocker explaining missing telemetry source.",
  "success_criteria": [
    "Model Health displays printing state",
    "Model Health displays progress percent when available",
    "Model Health displays time remaining when available",
    "No CAD/Fusion/geometry response"
  ],
  "missing_info": [
    "Whether Bambu telemetry source exposes progress and ETA"
  ],
  "clarification_needed": false,
  "clarification_question": "",
  "risk_level": "local_code_change",
  "route_candidates": [
    "codex_cli_ui_local_agent",
    "printer_status_capability"
  ],
  "forbidden_routes": [
    "cad_modeling_projects"
  ],
  "confidence": 0.91
}
```

The exact fields can evolve, but the app must have this kind of object. Without it, we are still guessing from keywords.

### 3. Clarification Gate

The app should ask a question back when:

- The target object is unclear.
- The requested end state is unclear.
- There are multiple plausible domains and the wrong domain would waste work or create risk.
- The user uses pronouns or "same/it/this/that" and the referent is not recoverable from recent context.
- A tool/action requires credentials, destructive writes, machine control, public publishing, or live hardware changes.
- Scientific or current factual questions need a source standard that is not specified.

The app should not ask when:

- A reasonable safe inspection can discover the answer.
- The missing data can be reported as a blocker after inspection.
- The user is asking a broad conceptual question and no action depends on the missing detail.

Clarification style:

- Ask one question.
- State the assumption or ambiguity in plain language.
- Do not include a full answer after the question unless a partial answer is useful and safe.

Example:

> I can do that, but I need one choice first: should percent/time remaining come from live Bambu telemetry, or is a temporary manual status override acceptable while we wire the live source?

### 4. Capability Registry

Replace project routing with capability routing. A project is organizational metadata. A capability is something the app can actually do.

Initial capability types:

- `conversation_answer`
- `current_web_research`
- `scientific_evidence_review`
- `local_file_retrieval`
- `codebase_inspection`
- `code_edit_and_verify`
- `app_ui_status_bug`
- `printer_status_readonly`
- `printer_control_sensitive`
- `cad_artifact_generation`
- `cad_reference_answer`
- `slicer_profile_workflow`
- `machine_inventory_update`
- `feedback_repair`
- `human_qa_workflow`

Each capability gets:

- Name.
- Scope.
- Required inputs.
- Refusal/clarification triggers.
- Tools allowed.
- Evidence standard.
- Verification standard.
- Output contract.
- Forbidden domains.

### 5. Route Vetoes

The system needs hard negative logic. Positive matches are not enough.

Examples:

- If `target_surface == codex_cli_ui.model_health`, veto CAD.
- If the prompt is about displayed app state, veto product-comparison research unless user asks why.
- If the prompt asks for scientific evidence, veto uncited generic advice.
- If the prompt asks to edit an existing local artifact, veto creating unrelated new artifacts.
- If a local file path is present, prefer local evidence retrieval before general knowledge.

### 6. Planner And Executor

For action requests, the app should run:

1. Frame.
2. Clarify if needed.
3. Plan.
4. Execute bounded tool calls.
5. Verify.
6. Compose answer.
7. Save trace.

This maps to ReAct-style reasoning and acting, but the internal reasoning should be summarized in trace events, not exposed as chain-of-thought.

Source: https://arxiv.org/abs/2210.03629

### 7. Evidence Policy

The app should classify evidence need:

- No external evidence needed: local preference, local status, simple math, codebase edits.
- Local evidence required: local file, machine inventory, app state, package health.
- Current web evidence required: current products, laws, specs, availability, prices, software versions.
- Scientific evidence required: peer-reviewed papers, datasheets, standards, test reports.
- Human evidence required: accessibility walkthroughs, subjective QA, live physical inspection.

The PET-CF annealing failure is this category:

- User did not ask "what is annealing?"
- User asked whether scientific evidence supports strength improvement in PET-CF.
- Correct behavior: retrieve scientific/datasheet/test evidence, distinguish tensile strength vs stiffness vs dimensional stability, identify formulation-specific uncertainty, and say when evidence is missing.

### 8. Response Composer

Separate "what to say" from "how to say it."

Inputs:

- Intent frame.
- Task result.
- Evidence summary.
- User tone.
- Risk level.
- Persona profile.

Output rules:

- First sentence answers or names the next required clarification.
- No mandatory "This is why" or "You should also consider" labels.
- Use varied natural transitions.
- When acting, say what changed and how verified.
- When blocked, say what was checked, what blocked it, and the next unblocker.
- When uncertain, say exactly what is uncertain.
- Keep the answer sized to the task.

Personality should come from stable voice rules plus generated variation, not from canned phrase blocks.

### 9. Feedback Learner

Learning must be explicit, auditable, and scoped. It should not mean "save this exact answer and repeat it."

For each feedback event, save:

```json
{
  "prompt": "...",
  "bad_answer": "...",
  "user_feedback": "...",
  "failure_kind": "misunderstood_target_surface",
  "bad_intent_frame": {},
  "corrected_intent_frame": {},
  "correct_route": "app_ui_status_bug",
  "forbidden_route": "cad_modeling_projects",
  "generalizable_lesson": "Requests about Model Health panel display fields are app UI/status-source work, not CAD.",
  "regression_prompt": "...",
  "required_trace": {
    "target_surface": "codex_cli_ui.model_health",
    "forbidden_routes": ["cad_modeling_projects"]
  },
  "required_answer_terms": ["Model Health", "Bambu H2D", "percent complete", "time remaining"],
  "forbidden_answer_terms": ["Fusion", "mounting hole", "STEP", "STL", "not enough geometry"],
  "verification": []
}
```

Good feedback should teach voice and usefulness patterns, but it should not clone exact structure.

Bad feedback should create:

- Corrected frame.
- Corrected route.
- One or more tests.
- A patch target.
- A recency-weighted lesson.

### 10. Trace And Eval System

Every run should have a structured trace:

- `input_normalized`
- `context_assembled`
- `intent_frame`
- `clarification_decision`
- `route_candidates`
- `route_vetoes`
- `selected_capability`
- `tool_plan`
- `tool_results`
- `verification`
- `response_composer_inputs`
- `final_answer`

Regression grading should move beyond final strings:

- Intent-frame accuracy.
- Clarification decision accuracy.
- Route precision and route recall.
- Veto correctness.
- Tool/evidence correctness.
- Answer usefulness.
- Personality variance.
- Latency.
- Human correction rate.

The existing 500 AI UI questions should be re-run with frame/route/answer grading, not only "did the answer contain expected words?"

## Recommended Rebuild Phases

### Phase 0: Stop The Bleeding

Goal: prevent more special-case growth while the new kernel is built.

Actions:

- Freeze new broad direct-answer branches unless they protect live reliability.
- Add a failing regression for the Bambu progress/ETA prompt, but do not fix it with another narrow detector.
- Add trace fields to `/api/run` responses behind a debug flag.
- Add a package-health check that verifies intent frame creation exists for core examples.

Exit criteria:

- Every `/api/run` has a generated frame in debug mode.
- Existing package health remains green.
- New tests prove the current bad behavior before replacement.

### Phase 1: Intent Frame In Front Of Legacy Router

Goal: understand before routing.

Actions:

- Create `server/intelligence/intent_frame.py` or equivalent.
- Add deterministic frame heuristics for obvious local app surfaces, files, printers, CAD, research, and feedback.
- Add optional LLM-assisted frame extraction when heuristics are not enough.
- Pass the frame into `route_manager()`.
- Add route vetoes that override legacy CAD/project matches.
- Add focused regression tests:
  - Bambu Model Health progress/ETA.
  - PET-CF scientific evidence request.
  - "fix it" with missing referent.
  - "do the same" with missing prior context.
  - local file evidence question.
  - current product/spec question.

Exit criteria:

- The Bambu progress/ETA request cannot route to CAD.
- The PET-CF scientific evidence request cannot produce generic process advice.
- Clarification gate asks one question when target/outcome is missing.

### Phase 2: Capability Registry

Goal: route to abilities, not projects.

Actions:

- Add a capability registry file, likely JSON plus Python handlers.
- Map frame fields to capability candidates.
- Each capability declares evidence, tool, risk, and output contracts.
- Let legacy direct-answer paths be called through capabilities where possible.
- Add "capability chosen" to trace and health receipts.

Exit criteria:

- App/product bug requests go to app-code capability.
- Printer status read-only and printer control sensitive are distinct.
- CAD reference and CAD artifact generation are distinct.
- Web research and scientific evidence review are distinct.

### Phase 3: Response Composer And Personality

Goal: make correct answers sound like a sharp teammate, not a compliance template.

Actions:

- Create `response_composer.py`.
- Remove global mandatory "This is why" insertion.
- Add tone modes based on task type, not random style.
- Add phrase-variation sets for common confirmations, blockers, clarifications, and evidence summaries.
- Add answer-size budgets by task.
- Add "personality lint" tests:
  - no repeated canned sections across adjacent runs,
  - no unrelated caveat line,
  - no raw internal route language,
  - no cold helpdesk phrasing when user is frustrated.

Exit criteria:

- Same task type across multiple prompts produces consistent judgment but varied phrasing.
- Direct answers are shorter and more natural.
- User feedback "Good/Fix this/Steer" updates voice lessons without cloning full answers.

### Phase 4: Feedback Learner

Goal: real improvement from every correction.

Actions:

- Store corrected intent frames from feedback.
- Generate route/trace/answer regressions automatically.
- Add a "lesson retrieval" layer that retrieves abstract lessons, not canned answers.
- Add a confidence decay or scope field so old lessons do not poison unrelated domains.
- Add review UI for generated lessons before promotion if the failure is broad.

Exit criteria:

- A failed answer creates a replayable test.
- A correction changes future routing/clarification behavior.
- The system can explain what it learned in one sentence.

### Phase 5: Monolith Reduction

Goal: reduce future fragility.

Actions:

- Move grouped capabilities out of `server.py`.
- Keep compatibility shims for old smoke tests.
- Convert direct-answer functions into capability handlers only when they are still valuable.
- Delete or quarantine stale branches after equivalent frame/capability tests pass.

Exit criteria:

- New functionality is added by defining a capability and tests, not by adding another global detector.
- `server.py` stops growing as the default solution.

## Implementation Principles

1. Do not trust keyword routing without a frame.
2. Do not answer a request until the target, action, and expected output are known or intentionally assumed.
3. Do not ask clarifying questions that safe inspection can answer.
4. Do not call personality a fix for wrong understanding.
5. Do not let feedback become canned answer cloning.
6. Do not let tests only grade final text.
7. Do not add specialists unless their tool, policy, or output contract differs.
8. Do not hide uncertainty; calibrate it.
9. Do not claim live/local/file evidence without retrieving it.
10. Do not let the app's internal architecture leak into Tinman's normal conversation.

## Example Correct Behaviors

### Bambu H2D Model Health Progress

User:

> in the model health for the bambu h2d it is now showing printing, which is good, but i als want it to display percent complete and time remaining on the print.

Correct response if implementation can proceed:

> Got it. You want the Bambu H2D Model Health card to show progress percent and time remaining, not just "printing." I am going to inspect the Model Health data source first; if the Bambu telemetry already exposes progress and ETA, I will wire those fields into the panel and verify the live health payload.

Correct response if blocked before acting:

> I understand the request: add percent complete and time remaining to the Bambu H2D Model Health card. The one thing I need to confirm is whether you want those values pulled only from live Bambu telemetry, or whether a temporary manual override is acceptable until the live source is wired.

Wrong response:

> I can design the part, but I do not have enough geometry...

### PET-CF Annealing Evidence

User:

> Does annealing PET-CF actually improve the strength?

Correct response shape:

> Maybe, but I would not claim it broadly without formulation-specific test data. For PET-CF the evidence has to separate stiffness, tensile strength, heat deflection, dimensional stability, and layer adhesion. I will look for datasheets or peer-reviewed/mechanical test results for the exact PET-CF family before recommending annealing as a strength upgrade.

Wrong response:

> Use annealing if you want higher stiffness and dimensional stability...

That answers process intent, not evidence intent.

## Build Decision

We should not terminate the project yet. There is enough useful local work here to salvage, but the next work must be architectural. If we keep adding direct answers and smoke cases, the app will continue to pass tests while failing Tinman's lived expectations.

The next pass should implement Phase 0 and Phase 1 only:

1. Add intent-frame generation.
2. Add trace output.
3. Add route vetoes.
4. Add six focused regressions.
5. Prove the Bambu progress/ETA prompt and PET-CF evidence prompt route correctly before any symptom-specific fixes.

That gives us the foundation for a personable subject-matter-expert interaction instead of another canned response layer.
