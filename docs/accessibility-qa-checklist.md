# Codex CLI UI Accessibility QA Checklist

Use this checklist before promoting accessibility audit items from `PARTIAL` to `PASS`.

## Keyboard

- Tab reaches New Chat, Projects, Admin, Chats, Tests, chat messages, attachment button, composer, Send, run controls, and Run Log in a predictable order.
- Shift Tab reverses through the same controls without trapping focus.
- Command Enter and Control Enter send or steer through the existing composer path.
- Command Period and Control Period stop an active run without requiring pointer use.
- Escape returns focus to the composer without cancelling an active run.
- Option C focuses chat messages, Option L focuses the run log, and Option N creates a new chat only when no run is active.

## Screen Reader

- VoiceOver announces chat messages as a log and identifies user versus Codex messages.
- The composer is announced as a message input with useful status text.
- Run state changes are announced without repeating the entire page, including request received, route ready, progress update, answer received, finalizing, complete, cancellation, recovery, and steer sent states.
- The Stop current run control is announced while a run is active and the cancelled state is announced after use.
- Attachment chips and local file links have names that describe the action.
- Error and recovery messages are read as normal answer content, not hidden diagnostic data.

## Visual Accessibility

- Main text, muted labels, warning text, danger text, and primary actions meet contrast expectations in light mode.
- Focus rings are visible on keyboard focus.
- Status is conveyed by text, icon/label, or placement, not color alone.
- At 150 percent and 200 percent text scaling, the composer, controls, and message cards remain usable without overlapping.
- Mobile width keeps the composer and run controls usable without horizontal scrolling.

## Motion

- With Reduce Motion enabled in macOS, transitions are effectively disabled.
- Health graphs and progress changes remain understandable without relying on animation.

## Media And Audio

- If the app ever produces or analyzes audio/video, the answer includes a text transcript, caption file, or concise text summary of the spoken content.
- Audio-only status is not required to understand an answer; the visible chat text remains the source of truth.
- Generated reports and artifacts that reference media include a clickable text receipt so the result is usable without hearing the media.

## Voice Input

- Text input remains the primary and fully functional path.
- Voice input, if added, is optional and never required to send, steer, edit, or review a message.
- Users can attach files, type prompts, edit questions, steer active runs, and use keyboard shortcuts without microphone permission.

## Slow Connections

- The app remains usable on a slow or intermittent connection by streaming text status, showing run state, and preserving local attachments/paths.
- Large local files use native-path attach when possible instead of forcing browser copy upload.
- Web, cloud research, live printer checks, and large downloads degrade with a clear blocker while local chat, cached manuals, source-vault evidence, and package-health checks remain usable.

## Plain Language

- Direct answers lead with the answer.
- Technical answers include a short “This is why” explanation.
- Follow-up risk or verification advice is in plain language and does not bury the answer.

## Manual Result

Record the tester, date, device, browser/app surface, and any failed item before changing the audit bank.
