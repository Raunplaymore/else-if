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


if __name__ == "__main__":
    unittest.main()
