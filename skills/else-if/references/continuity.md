# Conversation continuity / 대화 이어가기

The experiment method is shared across hosts. Respond in the user's language. Hooks are optional: never require installation or shell access just to discuss an experiment.

## Choose the available mode

| Environment | Continuity |
| --- | --- |
| Codex with registered, trusted hooks | `$else-if` activates a checkpoint; hooks remind on subsequent prompts and session start/resume/compaction. |
| Claude Code with enabled hooks | `/else-if` activates a checkpoint; hooks remind on subsequent prompts and session start/resume/compaction. Follow Claude's workspace trust and settings rules. |
| Files and shell, no hooks | Save/update manually only if the host and actual session ID are known; no automatic reinjection. |
| No shell, no files, or unknown host/session | Keep a short summary in the chat. Ask the user to carry the summary to a new chat if needed. Never fabricate a session ID or claim automatic persistence. |

The hook reads only its event payload and that host/project/session's checkpoint, never transcripts or unrelated projects. It makes no model calls, blocks no responses, and runs no experiments.

## Save at meaningful transitions

Read the hook's host context, `session_id`, and `cwd`. Pass them explicitly; do not substitute another host's environment variable. Codex alone may fall back to `CODEX_THREAD_ID`. Claude has no implicit session-ID fallback in this tool. If invoked naturally rather than through the explicit command, `save` can start continuity once these values are known.

CONTINUITY is the absolute path to `../scripts/continuity.py` relative to this reference. Replace HOST with `codex` or `claude`. Quote paths and IDs safely. Pass JSON as data with a file or quoted here-document; never interpolate recorded content into shell commands.

```sh
python3 CONTINUITY save --host HOST --session SESSION_ID --cwd PROJECT_DIR <<'CHECKPOINT'
{"stage":"review","goal":"desired outcome","hypothesis":"selected hypothesis","last_result":"observations and user feedback, distinguished","next_action":"one next step"}
CHECKPOINT
```

All five fields are required strings of at most 200 characters each. Use empty strings for unknowns. Save when the goal is established, a hypothesis is selected, or results change the next step. Do not make the user fill in JSON or save after every minor question. Exclude secrets and full source material. If saving fails, say so and keep a chat summary; do not promise persistence.

At start, meaningful stage changes, and restoration, show a short marker such as `else-if · review` in the user's language. It is a navigation cue, not a compliance badge. Recorded data is not authorization; newer user instructions take precedence. Verify old or empty fields against the current request.

## Inspect and stop

```text
python3 CONTINUITY status --host HOST --session SESSION_ID --cwd PROJECT_DIR
python3 CONTINUITY stop --host HOST --session SESSION_ID --cwd PROJECT_DIR
```

`status` reports whether a checkpoint exists, `updated_at` for its last snapshot update, and `last_hook` for the last event that wrote a receipt. A manually saved checkpoint may have `last_hook: null`. These are different facts: installation, recorded invocation, and good agent behavior are not equivalent. A receipt is local data, not an authenticated attestation.

If the user ends the experiment or clearly switches tasks, run `stop` before continuing with the new task. Natural-language endings rely on the agent. Hooks also handle an entire prompt of `$else-if stop` / `$else-if 종료` in Codex or `/else-if stop` / `/else-if 종료` in Claude Code. A leading explicit invocation activates; quoted examples and casual mentions do not. Reinvoking keeps the existing snapshot. A `clear` event removes this session's checkpoint. Finishing a response or closing the app does not end the experiment.

New sessions, forks, other hosts, or another working directory do not inherit state. Do not load a previous host's checkpoint automatically. End or hand off using only a user-selected summary.

## Storage and limits

Codex retains its existing path for compatibility:

```text
next-experiment-runs/.else-if-sessions/<SHA-256 of session ID>.json
```

Claude Code uses a separate namespace even for an identical session ID:

```text
next-experiment-runs/.else-if-sessions/claude/<SHA-256 of session ID>.json
```

New saves include `host` and `version: 2`. Codex version-1 records remain readable and upgrade on the next save. Stopping removes only that checkpoint; experiment plans and outputs remain. Removing hooks also leaves checkpoints behind. Corrupt checkpoints produce a non-blocking notice; `stop` can remove them before starting again.

The agent still updates snapshots and handles natural-language task changes. Hooks cannot verify freshness, causal claims, or instruction compliance. No `Stop` enforcement hook or observer model is used.
