#!/usr/bin/env python3
"""Register or remove only else-if hooks for Codex, Claude Code, or Gemini CLI."""

import argparse
import copy
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import uuid

MARKER = ": else-if-continuity-v1; "


def merge(config, command, remove=False, host="codex"):
    result = copy.deepcopy(config)
    if remove and "hooks" not in result:
        return result
    hooks = result.setdefault("hooks", {})
    for event in ("SessionStart", "BeforeAgent" if host == "gemini" else "UserPromptSubmit"):
        groups = []
        for group in hooks.get(event, []):
            kept = [h for h in group["hooks"] if not h.get("command", "").startswith(MARKER)]
            if kept:
                groups.append({**group, "hooks": kept})
        if not remove:
            handler = {"type": "command", "command": command, "timeout": 3000 if host == "gemini" else 3}
            if host == "codex":
                handler["additionalContextLimit"] = 2500
            if host == "gemini":
                handler["name"] = "else-if-continuity-" + event
            group = {"hooks": [handler]}
            if event == "SessionStart":
                group["matcher"] = "*" if host == "gemini" else "^(startup|resume|compact|clear)$"
            groups.append(group)
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--host", choices=("codex", "claude", "gemini"), default="codex")
    parser.add_argument("--config-dir", type=Path, help="Override the selected host's config directory")
    parser.add_argument("--check", action="store_true", help="Inspect installation only; does not prove hook execution or trust")
    args = parser.parse_args()
    if args.remove and args.check:
        parser.error("--remove and --check cannot be combined")
    if args.config_dir is not None:
        home = args.config_dir.expanduser().resolve()
    elif args.host == "codex":
        home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    elif args.host == "claude":
        home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    else:
        home = Path.home() / ".gemini"
    target = home / ("hooks.json" if args.host == "codex" else "settings.json")
    script = home / "skills/else-if/scripts/continuity.py"
    if not args.remove and not args.check and not script.is_file():
        parser.error("install the else-if skill link first")
    if target.is_symlink():
        parser.error("hook config is a symbolic link; inspect its destination before installing")
    quoted = shlex.quote(str(script))
    host_argument = f" --host {args.host}" if args.host != "codex" else ""
    inactive = " else echo '{}';" if args.host == "gemini" else ""
    command = MARKER + f"if [ -f {quoted} ]; then {shlex.quote(sys.executable)} {quoted} hook{host_argument};{inactive} fi"
    before = target.read_bytes() if target.exists() else None
    config = json.loads(before) if before is not None else {}
    if args.check:
        events = [event for event in ("SessionStart", "BeforeAgent" if args.host == "gemini" else "UserPromptSubmit")
                  if any(h.get("command") == command for g in config.get("hooks", {}).get(event, []) for h in g["hooks"])]
        print(json.dumps({"host": args.host, "skill_installed": (script.parents[1] / "SKILL.md").is_file(),
                          "hooks_registered": len(events) == 2, "registered_events": events,
                          "trust": "not_inspected; review in host", "execution": "not_proven; inspect continuity.py status"}))
        return
    result = merge(config, command, args.remove, args.host)
    if result == config:
        print("Already configured; no change.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if before is not None:
        backup = target.with_name(target.name + ".else-if-backup-" + uuid.uuid4().hex)
        with backup.open("xb") as stream:
            stream.write(before)
        backup.chmod(0o600)
        print(f"Backup: {backup}")
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".else-if-hooks-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if (target.read_bytes() if target.exists() else None) != before:
            raise RuntimeError("hook config changed during installation; retry after inspecting it")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    menu = "/hooks panel" if args.host == "gemini" else "/hooks"
    print("else-if hooks removed." if args.remove else f"Two else-if hooks registered for {args.host}. Review them in the host {menu} menu before use.")


if __name__ == "__main__":
    main()
