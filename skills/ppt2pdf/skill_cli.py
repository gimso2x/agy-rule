#!/usr/bin/env python3
"""User-facing ppt2pdf fast-path CLI.

Public contract:
  ppt2pdf [run] <url> [run options]
  ppt2pdf check
  ppt2pdf status
  ppt2pdf cleanup

Unknown first tokens are treated as run input. The legacy ppt2pdf.py remains the
capture engine; Markdown conversion is opt-in at this wrapper boundary.
"""
from __future__ import annotations

import importlib.util
import json
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
    markdown = False
    forwarded: list[str] = []
    for arg in argv:
        if arg == "--markdown":
            markdown = True
        else:
            forwarded.append(arg)

    if not markdown and "--no-markdown" not in forwarded:
        forwarded.append("--no-markdown")

    original_argv = sys.argv
    try:
        sys.argv = [str(Path(engine.__file__).resolve()), *forwarded]
        engine.main()
    finally:
        sys.argv = original_argv
    return 0


def browser_state() -> dict[str, object]:
    alive = engine.chrome_alive()
    state: dict[str, object] = {
        "port": engine.PORT,
        "profile": str(engine.PROFILE),
        "profile_exists": engine.PROFILE.is_dir() and not engine.PROFILE.is_symlink(),
        "chromium_available": engine.find_chromium() is not None,
        "cdp": "down",
        "pid": None,
    }
    if alive:
        try:
            state["pid"] = engine.profile_bound()
            state["cdp"] = "ready"
        except SystemExit as exc:
            state["cdp"] = "foreign-or-invalid"
            state["reason"] = str(exc)
    return state


def cmd_check() -> int:
    state = browser_state()
    state.update(
        playwright=importlib.util.find_spec("playwright") is not None,
        img2pdf=importlib.util.find_spec("img2pdf") is not None,
    )
    state["ready"] = bool(
        state["playwright"]
        and state["img2pdf"]
        and state["chromium_available"]
        and state["cdp"] in {"ready", "down"}
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
            for path in engine.WORK.glob("slide-*.png"):
                if path.is_file() and not path.is_symlink():
                    path.unlink()
                    removed += 1
    finally:
        lock.close()
    print(json.dumps({"removed_temp_slides": removed, "work_dir": str(engine.WORK)}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    command, rest = split_command(list(sys.argv[1:] if argv is None else argv))
    if command == "run":
        return cmd_run(rest)
    if rest:
        print(f"ppt2pdf: {command} takes no arguments", file=sys.stderr)
        return 2
    if command == "check":
        return cmd_check()
    if command == "status":
        return cmd_status()
    return cmd_cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
