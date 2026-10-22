# else-if

[한국어](README.md) · English

**Stuck repeating the same approach? Choose one small change to test next.**

else-if is an Agent Skills workflow for separating hypotheses, recommending a small comparison, and using the result to decide what to keep or change. It uses your current AI host's model and tools; it does not run a separate model service.

## When to use it

- Revisions keep happening without a clear explanation of what is wrong.
- Several approaches seem plausible and you need to choose what to test first.
- A result is somewhat better, but you need to decide what to preserve next.

The flow is: **goal and evidence → up to three candidates → one recommendation → comparison → review**. It preserves previous outputs, distinguishes measurements from user judgments, and changes hypotheses when the same complaint remains. Routine fixes and implementation with an established approach do not need this workflow.

## Support and verification

| Environment | Skill | Optional continuity | Verification |
| --- | --- | --- | --- |
| Local Codex | `$else-if` | Prompt and session-start hooks | Automated lifecycle/install/isolation tests; earlier user feedback. Revised model behavior is not end-to-end verified. |
| Local Claude Code | `/else-if` | Prompt and session-start hooks | Official event contract, installed-command execution, lifecycle and settings-preservation tests. Model conversations are not end-to-end verified. |
| Chat without files or shell | Provide the instructions and keep a chat summary | Manual | No automatic persistence claim. |
| Gemini CLI and other hosts | Not verified by this project | No adapter yet | Future integration targets. |

The common [Agent Skills format](https://agentskills.io/specification) does not make hook runtimes interchangeable. Local Claude Code setup is not a claim of support for Claude web, Cowork, or cloud sessions.

## Install the skill

You need Codex or Claude Code and Git. The helper programs and hooks need Python 3.9+ with no third-party Python packages or separate API key. Commands below use a macOS/Linux POSIX shell; automated tests were run on macOS with Python 3.11. Windows installation is not verified.

```sh
git clone https://github.com/Raunplaymore/else-if.git
cd else-if
```

Choose one host, or install each separately:

**Codex**

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s "$PWD/skills/else-if" "${CODEX_HOME:-$HOME/.codex}/skills/else-if"
```

**Claude Code**

```sh
mkdir -p "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
ln -s "$PWD/skills/else-if" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/else-if"
```

Existing entries are not overwritten. Keep the checkout in place: moving or deleting it breaks the link. If discovery has not refreshed, start a new chat or restart the host. You can also give an agent the absolute path to `skills/else-if/SKILL.md` and ask it to read and use the skill.

In your working project's chat:

```text
$else-if I keep revising this design without getting closer to the intended direction.
Compare the requests, outputs, and feedback and recommend the next small experiment.
```

In Claude Code, replace `$else-if` with `/else-if`. Follow up naturally, for example: “Try the first one with a 30-minute budget and no extra spend,” then “The colors changed, but the underlying issue remains.” Users do not need to fill in JSON forms for ordinary discussion.

## Optional: conversation continuity hooks

From the else-if checkout, choose the host:

```sh
python3 scripts/install_continuity.py --host codex
# For Claude Code, use this instead:
# python3 scripts/install_continuity.py --host claude
```

The installer backs up and merges only else-if entries into the selected user's config: Codex `hooks.json` or Claude Code `settings.json`. Existing settings, unrelated hooks, and trust decisions are preserved. The registered events are `UserPromptSubmit` and `SessionStart` (startup, resume, compact, clear).

Review the two `else-if-continuity-v1` entries in the host's `/hooks` menu. Codex requires trusting new definitions. Claude Code applies its own workspace trust and settings rules. Reload or restart if new entries are not visible. See [Codex hooks](https://learn.chatgpt.com/docs/hooks) and [Claude Code hooks](https://code.claude.com/docs/en/hooks).

Check configuration without changing it:

```sh
python3 scripts/install_continuity.py --host codex --check
# Use --host claude for Claude Code.
```

This reports discovery and expected hook registration, not trust or execution. A leading `$else-if` in Codex or `/else-if` in Claude activates a small checkpoint; subsequent prompts and session resume/compaction reinject it. Quoted examples and casual mentions do not activate it. Natural-language activation can also be handled by the agent when the actual host and session ID are known.

End continuity with an entire message of `$else-if stop` in Codex or `/else-if stop` in Claude Code. Natural-language endings and task switches rely on the agent to stop the checkpoint. Plans and experiment outputs remain.

### What is stored?

Five short fields: goal, hypothesis, last result, next action, and stage. Each has a 200-character limit. Checkpoints live under your working project's `next-experiment-runs/.else-if-sessions/`; Claude uses a separate `claude/` namespace. Existing Codex version-1 records remain readable and upgrade on the next save.

No full transcript collection, cross-project scanning, automatic host/session handoff, extra model call, response blocking, or forced rerun is performed. At meaningful transitions the agent is instructed to show a short stage marker. This is not a compliance badge.

Ask the agent to inspect continuity status using the actual host/session/workspace. `updated_at` records when the snapshot was saved. `last_hook` records the last hook event and time, or is null for a manually saved checkpoint with no hook invocation. A local receipt does not prove correct reasoning or instruction compliance. Snapshots still depend on agent updates and may become stale. See [continuity instructions](skills/else-if/references/continuity.md).

## No files or hooks available?

Provide the skill instructions as readable text. The agent should keep a short summary of the goal, hypothesis, last result, next action, and stage in the conversation. Carry that summary to another chat manually if needed. It must not invent session IDs, demand hook installation, claim files were saved, or imply automatic restoration.

## Optional: compare numerical results

From the checkout:

```sh
python3 skills/else-if/scripts/experiment.py check examples/design-plan.json
python3 skills/else-if/scripts/experiment.py review examples/design-plan.json examples/design-results.json
```

Both example files are synthetic. `check` validates and fingerprints a plan. `review` compares paired submitted measurements and accounts for missing trials, failures, deviations, budget overruns, and guardrail regressions. The example verdict is `criteria_met`: submitted values meet the recorded criteria. It does not establish source authenticity, causal effects, statistical significance, or live budget enforcement.

The comparison program only reads its specified input files; it does not write files, run source commands, or access the network. See the [record contract](skills/else-if/references/record-format.md).

```sh
python3 -m unittest discover -s tests -v
```

See [behavioral validation scenarios](tests/BEHAVIORAL.md) for the distinction between automated protocol tests and real model conversations.

## Update, disable, remove

Update with `git pull --ff-only` from the checkout. If hook definitions or their command paths change, rerun the installer for your chosen host and review any new trust requirement.

To disable implicit selection in Codex, append this to `skills/else-if/agents/openai.yaml`:

```yaml
policy:
  allow_implicit_invocation: false
```

That setting is Codex-specific; follow Claude Code's settings for its selection and permission controls. Explicit invocation remains available in Codex. Stop an already-active checkpoint separately.

Remove the hooks first, then the skill link, from the checkout:

```sh
python3 scripts/install_continuity.py --host codex --remove
test -L "${CODEX_HOME:-$HOME/.codex}/skills/else-if" && unlink "${CODEX_HOME:-$HOME/.codex}/skills/else-if"
```

For Claude Code:

```sh
python3 scripts/install_continuity.py --host claude --remove
test -L "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/else-if" && unlink "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/else-if"
```

Reload the host's settings. Instructions already read into a conversation are not erased by unlinking; ask the agent to stop or start a fresh chat. Project records and config backups are retained for separate cleanup.

## Limits

This is a skill and helper tools, without a separate application, autonomous experiment runner, or automatic policy mutation. Earlier user feedback suggests it can make the next decision more concrete; general quality or performance improvements are not established. Your host's data-processing policies and model usage charges still apply.
