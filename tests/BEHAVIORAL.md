# Behavioral validation / 실제 대화 검증

Automated tests exercise file validation, host-scoped checkpoints, official hook event payloads, installed shell commands, and config preservation. They do not prove that a model follows the workflow during an actual conversation.

## Current evidence

- Python tests: Codex and Claude Code event contracts, multi-turn checkpoint retention, resume/compact, explicit stop, cross-host/session/project isolation, legacy Codex state, non-blocking corruption, and install/remove/check behavior.
- Local Claude Code version observed: 2.1.293. Its native `doctor` completed with the generated settings in an isolated config directory and no settings-validation error. It reported missing authentication and a keychain warning; no model-backed Claude behavioral run was performed. This check does not establish hook delivery to a model.
- Codex: earlier qualitative user feedback exists for the prior workflow. The current cross-host revision has not been exercised end-to-end in a model conversation.
- No live Gemini CLI or Windows verification.

## Run the same scenario in each host

Use a disposable local project with two small UI drafts or other comparable outputs; do not use production data or deployment tools. Install the skill and optional hooks using that host's documented review procedure. Record host version and the actual session ID. Keep outputs and a concise transcript excerpt in the disposable workspace. Budget the run before starting; do not retry indefinitely or call paid APIs without authorization.

1. Begin with `$else-if` in Codex or `/else-if` in Claude: “The settings screen still feels crowded after three revisions. Keep the dark theme and all existing controls. What should we test next?”
2. Select one proposed experiment. Ask for a comparison within a small fixed budget.
3. Reply: “Somewhat better, but the hierarchy still feels unclear.”
4. Ask a short related question: “What exactly would we measure here?”
5. Compact or resume the same conversation through the host's normal controls. Then ask: “What are we testing now, and what did we learn?”
6. Switch tasks clearly: “Stop this experiment. Now help me rewrite this meeting invitation.”
7. Try an explicit stop separately in another run. Start another session and the other host in the same project and confirm that neither inherits the first run's checkpoint.

## Evaluate observed behavior

- The agent preserves the requested screen, dark direction, and controls; it does not silently substitute another problem.
- Later turns retain the selected hypothesis, honest feedback, budget, and next action rather than starting over or inventing evidence.
- “Somewhat better” is treated as partial improvement, not full success or release approval.
- A snapshot is actually saved at meaningful transitions; hook receipt and snapshot update timestamps are distinguished.
- After compaction/resume, the agent can identify the current experiment from available evidence; state that was never saved is not invented.
- An unrelated task is answered without forcing an experiment; the agent stops the checkpoint on a clear switch.
- Explicit stop removes only the matching host/session checkpoint; other sessions, hosts, plans and output files remain intact.
- With hooks disabled, the agent uses a manual summary without claiming automatic injection. Without file/shell access it does not require installation or fabricate a session ID.

Report actual actions, artifacts, failures, and unknowns. A displayed `else-if` marker, valid JSON, or hook receipt alone does not count as a behavioral pass. Record the result of each model-backed run separately; do not label these planned scenarios as executed.
