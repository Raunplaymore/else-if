import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/else-if/scripts/continuity.py"


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


continuity = module(SCRIPT)
installer = module(ROOT / "scripts/install_continuity.py")


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cwd = str(Path(self.temp.name).resolve())
        self.session = "session-a"
        self.snapshot = dict(stage="검토", goal="어두운 홈", hypothesis="카드 표현",
                             last_result="부분 개선", next_action="원본 아트 비교")

    def event(self, prompt="계속해", **extra):
        return dict(hook_event_name="UserPromptSubmit", cwd=self.cwd,
                    session_id=self.session, prompt=prompt, **extra)

    def cli(self, command, data=None, **env):
        return subprocess.run([sys.executable, str(SCRIPT), command], cwd=self.cwd,
                              input=json.dumps(data) if data is not None else "",
                              text=True, capture_output=True,
                              env={**os.environ, "CODEX_THREAD_ID": self.session, **env})

    def test_unrelated_and_quoted_mentions_do_not_activate_or_write(self):
        for prompt in ("안녕", "else-if가 뭐야", "`$else-if` 사용법", "예: $else-if 문제", "$else-if-other"):
            self.assertIsNone(continuity.hook(self.event(prompt)))
        self.assertEqual(list(Path(self.cwd).iterdir()), [])

    def test_multiturn_save_resume_compact_then_stop(self):
        self.assertIn("additionalContext", continuity.hook(self.event("$else-if 홈 개선"))["hookSpecificOutput"])
        saved = self.cli("save", self.snapshot)
        self.assertEqual(saved.returncode, 0, saved.stderr)
        for event in (self.event(), self.event("조금 나아졌어")):
            result = continuity.hook(event)
            self.assertIn("카드 표현", json.loads(result["hookSpecificOutput"]["additionalContext"].split("\n", 1)[1])["snapshot"]["hypothesis"])
        for source in ("startup", "resume", "compact"):
            event = dict(hook_event_name="SessionStart", cwd=self.cwd, session_id=self.session, source=source)
            self.assertIsNotNone(continuity.hook(event))
        continuity.hook(self.event("$else-if 종료"))
        self.assertIsNone(continuity.hook(self.event()))

    def test_session_and_project_isolation(self):
        continuity.save(self.cwd, self.session, self.snapshot)
        event = self.event()
        event["session_id"] = "session-b"
        self.assertIsNone(continuity.hook(event))
        other = Path(self.cwd) / "other"
        other.mkdir()
        event.update(session_id=self.session, cwd=str(other))
        self.assertIsNone(continuity.hook(event))
        event.update(cwd=self.cwd, hook_event_name="SessionStart", source="fork")
        self.assertIsNone(continuity.hook(event))

    def test_reinvocation_keeps_latest_state_clear_removes_only_checkpoint(self):
        continuity.save(self.cwd, self.session, self.snapshot)
        plan = Path(self.cwd) / "next-experiment-runs/plan.md"
        plan.write_text("keep")
        continuity.hook(self.event("$else-if 계속"))
        self.assertEqual(continuity.load(self.cwd, self.session)["snapshot"], self.snapshot)
        continuity.hook(dict(hook_event_name="SessionStart", cwd=self.cwd, session_id=self.session, source="clear"))
        self.assertIsNone(continuity.load(self.cwd, self.session))
        self.assertEqual(plan.read_text(), "keep")

    def test_stop_cli_and_exact_stop_prompt(self):
        for prompt in ("$else-if stop", "$else-if 종료."):
            continuity.save(self.cwd, self.session, self.snapshot)
            continuity.hook(self.event(prompt))
            self.assertIsNone(continuity.load(self.cwd, self.session))
        continuity.save(self.cwd, self.session, self.snapshot)
        self.assertEqual(self.cli("stop").returncode, 0)
        self.assertFalse(json.loads(self.cli("status").stdout)["active"])

    def test_corrupt_or_invalid_hook_input_never_blocks(self):
        continuity.save(self.cwd, self.session, self.snapshot)
        _, path = continuity.identity(self.cwd, self.session)
        path.write_text("broken")
        for data in (self.event(), {"hook_event_name": "UserPromptSubmit"}, []):
            run = self.cli("hook", data)
            self.assertEqual(run.returncode, 0, run.stderr)
            response = json.loads(run.stdout)
            self.assertIn("systemMessage", response)
            self.assertNotIn("decision", response)

    def test_bounds_and_symlinks_are_rejected(self):
        for session in ("../escape", "", None):
            with self.assertRaises(ValueError):
                continuity.save(self.cwd, session, self.snapshot)
        bad = {**self.snapshot, "goal": "x" * 201}
        with self.assertRaises(ValueError):
            continuity.save(self.cwd, self.session, bad)
        outside = Path(self.cwd) / "outside"
        outside.mkdir()
        (Path(self.cwd) / "next-experiment-runs").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            continuity.save(self.cwd, self.session, self.snapshot)
        self.assertEqual(list(outside.iterdir()), [])

    def test_snapshot_and_prompt_are_data_not_executed_or_archived(self):
        marker = Path(self.cwd) / "DO_NOT_CREATE"
        snapshot = {**self.snapshot, "hypothesis": f"$(touch {marker})"}
        continuity.save(self.cwd, self.session, snapshot)
        response = continuity.hook(self.event("PRIVATE_RAW_PROMPT", transcript_path="/do/not/read"))
        self.assertNotIn("PRIVATE_RAW_PROMPT", json.dumps(response))
        self.assertFalse(marker.exists())
        _, path = continuity.identity(self.cwd, self.session)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_install_merge_preserves_existing_hooks_and_is_idempotent(self):
        original = {"description": "existing", "hooks": {
            "SessionStart": [{"matcher": "resume", "hooks": [{"type": "command", "command": "existing"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "leave-alone"}]}]}}
        before = copy.deepcopy(original)
        command = installer.MARKER + "echo example"
        installed = installer.merge(original, command)
        self.assertEqual(original, before)
        self.assertEqual(installed["hooks"]["SessionStart"][0], original["hooks"]["SessionStart"][0])
        self.assertEqual(installer.merge(installed, command), installed)
        self.assertEqual(installer.merge(installed, command, remove=True), original)

    def test_installer_cli_backups_and_removal(self):
        home = Path(self.cwd) / "codex"
        skill = home / "skills/else-if"
        skill.parent.mkdir(parents=True)
        skill.symlink_to(SCRIPT.parents[1], target_is_directory=True)
        config = home / "hooks.json"
        before = b'{"description":"keep", "hooks":{}}'
        config.write_bytes(before)
        cmd = [sys.executable, str(ROOT / "scripts/install_continuity.py")]
        env = {**os.environ, "CODEX_HOME": str(home)}
        run = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        backups = list(home.glob("hooks.json.else-if-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)
        again = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(len(list(home.glob("hooks.json.else-if-backup-*"))), 1)
        removed = subprocess.run(cmd + ["--remove"], env=env, capture_output=True, text=True)
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertEqual(json.loads(config.read_text()), json.loads(before))

    def test_claude_multiturn_lifecycle_and_independent_stop(self):
        continuity.save(self.cwd, self.session, self.snapshot)
        event = self.event("/else-if improve the home", permission_mode="default")
        response = continuity.hook(event, "claude")
        self.assertEqual(response["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        next_snapshot = {**self.snapshot, "last_result": "partial improvement, not release approval"}
        continuity.save(self.cwd, self.session, next_snapshot, "claude")
        for prompt in ("Try the first one", "Somewhat better", "What does this metric mean?"):
            response = continuity.hook(self.event(prompt), "claude")
            state = json.loads(response["hookSpecificOutput"]["additionalContext"].split("\n", 1)[1])
            self.assertEqual(state["snapshot"], next_snapshot)
            self.assertEqual(state["host"], "claude")
        for source in ("resume", "compact"):
            event = dict(hook_event_name="SessionStart", cwd=self.cwd, session_id=self.session, source=source)
            self.assertIsNotNone(continuity.hook(event, "claude"))
        continuity.hook(self.event("/else-if stop"), "claude")
        self.assertIsNone(continuity.load(self.cwd, self.session, "claude"))
        self.assertEqual(continuity.load(self.cwd, self.session)["snapshot"], self.snapshot)

    def test_claude_ignores_codex_syntax_quotes_and_other_sessions(self):
        for prompt in ("$else-if goal", "`/else-if` example", "Example: /else-if goal", "/else-if-other"):
            self.assertIsNone(continuity.hook(self.event(prompt), "claude"))
        self.assertEqual(list(Path(self.cwd).iterdir()), [])
        continuity.hook(self.event("/else-if goal"), "claude")
        other = {**self.event(), "session_id": "different"}
        self.assertIsNone(continuity.hook(other, "claude"))
        self.assertIsNone(continuity.hook(self.event()))
        continuity.hook(dict(hook_event_name="SessionStart", cwd=self.cwd,
                             session_id=self.session, source="clear"), "claude")
        self.assertIsNone(continuity.load(self.cwd, self.session, "claude"))

    def test_last_hook_receipt_does_not_claim_snapshot_was_updated(self):
        state = continuity.save(self.cwd, self.session, self.snapshot, "claude")
        self.assertIsNone(state["last_hook"])
        continuity.hook(self.event(), "claude")
        updated = continuity.load(self.cwd, self.session, "claude")
        self.assertEqual(updated["updated_at"], state["updated_at"])
        self.assertEqual(updated["last_hook"]["event"], "UserPromptSubmit")
        self.assertTrue(updated["last_hook"]["at"])
        continuity.save(self.cwd, self.session, self.snapshot, "claude")
        self.assertEqual(continuity.load(self.cwd, self.session, "claude")["last_hook"], updated["last_hook"])

    def test_legacy_codex_records_remain_readable_and_upgrade_on_save(self):
        root, path = continuity.identity(self.cwd, self.session)
        path.parent.mkdir(parents=True)
        old = {"version": 1, "session_id": self.session, "cwd": str(root),
               "updated_at": "2026-10-22T00:00:00+00:00", "snapshot": self.snapshot}
        path.write_text(json.dumps(old))
        self.assertEqual(continuity.load(self.cwd, self.session)["snapshot"], self.snapshot)
        self.assertIsNone(continuity.load(self.cwd, self.session, "claude"))
        continuity.save(self.cwd, self.session, self.snapshot)
        self.assertEqual(continuity.load(self.cwd, self.session)["version"], 2)

    def test_claude_cli_requires_explicit_session_and_rejects_symlink_namespace(self):
        run = subprocess.run([sys.executable, str(SCRIPT), "status", "--host", "claude"],
                             env={**os.environ, "CODEX_THREAD_ID": self.session},
                             cwd=self.cwd, capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        base = Path(self.cwd) / "next-experiment-runs/.else-if-sessions"
        base.mkdir(parents=True)
        outside = Path(self.cwd) / "outside"
        outside.mkdir()
        (base / "claude").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            continuity.save(self.cwd, self.session, self.snapshot, "claude")
        self.assertEqual(list(outside.iterdir()), [])

    def test_claude_installer_preserves_settings_check_and_removal(self):
        home = Path(self.cwd) / "claude-config"
        skill = home / "skills/else-if"
        skill.parent.mkdir(parents=True)
        skill.symlink_to(SCRIPT.parents[1], target_is_directory=True)
        config = home / "settings.json"
        original = {"model": "keep-existing", "permissions": {"allow": ["Read"]},
                    "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "existing"}]}]}}
        before = json.dumps(original).encode()
        config.write_bytes(before)
        cmd = [sys.executable, str(ROOT / "scripts/install_continuity.py"), "--host", "claude"]
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(home)}
        checked = subprocess.run(cmd + ["--check"], env=env, capture_output=True, text=True, check=True)
        self.assertFalse(json.loads(checked.stdout)["hooks_registered"])
        self.assertEqual(config.read_bytes(), before)
        subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        installed = json.loads(config.read_text())
        self.assertEqual(installed["model"], original["model"])
        self.assertEqual(installed["permissions"], original["permissions"])
        handler = installed["hooks"]["SessionStart"][-1]["hooks"][0]
        self.assertNotIn("additionalContextLimit", handler)
        checked = subprocess.run(cmd + ["--check"], env=env, capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(checked.stdout)["hooks_registered"])
        # Execute exactly the installed command using the native event payload contract.
        prompt_handler = installed["hooks"]["UserPromptSubmit"][-1]["hooks"][0]
        run = subprocess.run(["/bin/sh", "-c", prompt_handler["command"]],
                             input=json.dumps(self.event("/else-if test")), cwd=self.cwd,
                             capture_output=True, text=True, check=True)
        self.assertIn("additionalContext", json.loads(run.stdout)["hookSpecificOutput"])
        self.assertIsNotNone(continuity.load(self.cwd, self.session, "claude"))
        save = subprocess.run([sys.executable, str(SCRIPT), "save", "--host", "claude",
                               "--session", self.session], input=json.dumps(self.snapshot),
                              cwd=self.cwd, capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(save.stdout)["saved"])
        for payload in (self.event("Somewhat better"),
                        {"hook_event_name": "SessionStart", "source": "compact",
                         "cwd": self.cwd, "session_id": self.session}):
            run = subprocess.run(["/bin/sh", "-c", prompt_handler["command"]], input=json.dumps(payload),
                                 cwd=self.cwd, capture_output=True, text=True, check=True)
            state = json.loads(json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"].split("\n", 1)[1])
            self.assertEqual(state["snapshot"], self.snapshot)
        subprocess.run(["/bin/sh", "-c", prompt_handler["command"]],
                       input=json.dumps(self.event("/else-if stop")), cwd=self.cwd,
                       capture_output=True, text=True, check=True)
        self.assertIsNone(continuity.load(self.cwd, self.session, "claude"))
        subprocess.run(cmd + ["--remove"], env=env, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(config.read_text()), original)
        self.assertTrue(any(p.read_bytes() == before for p in home.glob("settings.json.else-if-backup-*")))

    def test_uninstall_without_existing_hooks_is_a_noop(self):
        self.assertEqual(installer.merge({}, "unused", remove=True, host="claude"), {})


if __name__ == "__main__":
    unittest.main()
