#!/usr/bin/env python3
"""User-facing ppt2pdf fast-path CLI.

Public contract:
  ppt2pdf [run] <url> [run options]
  ppt2pdf check
  ppt2pdf status
  ppt2pdf cleanup

Unknown first tokens are treated as run input. This wrapper only captures PDF/PNGs;
the invoking agent completes Markdown by directly reading the images (SKILL.md).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

try:
    from . import ppt2pdf as engine
except ImportError:
    import ppt2pdf as engine

COMMANDS = {"run", "check", "status", "cleanup"}


def split_command(argv: list[str]) -> tuple[str, list[str]]:
    if argv and argv[0] in COMMANDS:
        return argv[0], argv[1:]
    return "run", argv


def cmd_run(argv: list[str]) -> int:
    markdown = "--no-markdown" not in argv
    forwarded = [arg for arg in argv if arg not in {"--markdown", "--no-markdown"}]
    # Never invoke the legacy external-proxy converter. Markdown belongs to the
    # invoking agent, including when --markdown was explicitly requested.
    forwarded.append("--no-markdown")

    original_argv = sys.argv
    try:
        sys.argv = [str(Path(engine.__file__).resolve()), *forwarded]
        engine.main()
    finally:
        sys.argv = original_argv
    if markdown:
        print("ppt2pdf: capture complete; invoking agent must now transcribe slide-*.png "
              "into <document>.md directly, following SKILL.md.", file=sys.stderr)
    return 0


def browser_state() -> dict[str, object]:
    ego_bin = engine.find_ego_browser()
    ego_ok = engine.ego_alive() if ego_bin else False

    profiles_info = []
    if ego_ok and ego_bin:
        try:
            r = subprocess.run([ego_bin, 'nodejs'], input='console.log(JSON.stringify(await profiles()));',
                               capture_output=True, text=True, timeout=5)
            for line in (r.stdout + r.stderr).splitlines():
                if line.strip().startswith('['):
                    profiles_info = json.loads(line.strip())
                    break
        except Exception:
            pass

    state: dict[str, object] = {
        "engine": "ego-browser",
        "ego_browser": ego_bin,
        "ego_available": ego_ok,
        "profiles": profiles_info,
        "work_dir": str(engine.WORK),
        # 하위 호환성 키
        "port": engine.PORT,
        "profile": str(engine.PROFILE),
        "profile_exists": True,
        "chromium_available": ego_bin is not None,
        "cdp": "ready" if ego_ok else "down",
        "pid": 0 if ego_ok else None,
    }
    return state


def cmd_check() -> int:
    state = browser_state()
    state.update(
        playwright=importlib.util.find_spec("playwright") is not None,
        img2pdf=importlib.util.find_spec("img2pdf") is not None,
    )
    state["ready"] = bool(
        state["img2pdf"]
        and state["ego_available"]
    )
    print(json.dumps(state, ensure_ascii=False, sort_keys=True))
    return 0 if state["ready"] else 2


def cmd_status() -> int:
    print(json.dumps(browser_state(), ensure_ascii=False, sort_keys=True))
    return 0


def cmd_cleanup() -> int:
    # Reuse the engine's non-blocking flock. If another capture owns the lock,
    # acquire_run_lock fails instead of racing its temporary slide directory.
    lock = engine.acquire_run_lock()
    removed = 0
    try:
        if engine.WORK.is_dir():
            for f in engine.WORK.glob("slide-*.png"):
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
    finally:
        lock.close()
    print(json.dumps({"removed_temp_slides": removed, "work_dir": str(engine.WORK)},
                     ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd, rest = split_command(argv)
    if cmd == "run":
        return cmd_run(rest)
    if cmd == "check":
        return cmd_check()
    if cmd == "status":
        return cmd_status()
    if cmd == "cleanup":
        return cmd_cleanup()
    return 1


if __name__ == "__main__":
    sys.exit(main())
