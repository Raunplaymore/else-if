#!/usr/bin/env python3
"""Register or remove only else-if hooks; never change Codex hook trust."""

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


def merge(config, command, remove=False):
    result = copy.deepcopy(config)
    hooks = result.setdefault("hooks", {})
    for event in ("SessionStart", "UserPromptSubmit"):
        groups = []
        for group in hooks.get(event, []):
            kept = [h for h in group["hooks"] if not h.get("command", "").startswith(MARKER)]
            if kept:
                groups.append({**group, "hooks": kept})
        if not remove:
            group = {"hooks": [{"type": "command", "command": command,
                                "timeout": 3, "additionalContextLimit": 2500}]}
            if event == "SessionStart":
                group["matcher"] = "^(startup|resume|compact|clear)$"
            groups.append(group)
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    target = home / "hooks.json"
    script = home / "skills/else-if/scripts/continuity.py"
    if not args.remove and not script.is_file():
        parser.error("install the else-if skill link first")
    if target.is_symlink():
        parser.error("hooks.json is a symbolic link; inspect its destination before installing")
    quoted = shlex.quote(str(script))
    command = MARKER + f"if [ -f {quoted} ]; then {shlex.quote(sys.executable)} {quoted} hook; fi"
    before = target.read_bytes() if target.exists() else None
    config = json.loads(before) if before is not None else {}
    result = merge(config, command, args.remove)
    if result == config:
        print("Already configured; no change.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if before is not None:
        backup = target.with_name("hooks.json.else-if-backup-" + uuid.uuid4().hex)
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
            raise RuntimeError("hooks.json changed during installation; retry after inspecting it")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("else-if hooks removed." if args.remove else "Two else-if hooks registered. Review and trust them in Codex /hooks before use.")


if __name__ == "__main__":
    main()
