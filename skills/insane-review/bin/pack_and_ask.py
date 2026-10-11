#!/usr/bin/env python3
"""Trusted launcher for the immutable, validated Insane Review generation."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]
VENDOR = ROOT / "vendor"


def fail(message: str) -> None:
    raise SystemExit(f"insane-review launcher: {message}")


def checked_directory(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o022:
        fail(f"unsafe directory: {path}")


def digest_fd(fd: int) -> str:
    digest = hashlib.sha256()
    while block := os.read(fd, 1 << 20):
        digest.update(block)
    return digest.hexdigest()


def generation_fd() -> int:
    # Resolve every ancestor before opening `current`; no resolved path is used later.
    for ancestor in (ROOT, VENDOR, VENDOR / "generations"):
        checked_directory(ancestor)
    current_fd = os.open(VENDOR / "current", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        current_info = os.fstat(current_fd)
        if not stat.S_ISREG(current_info.st_mode) or stat.S_IMODE(current_info.st_mode) & 0o022:
            fail("vendor/current is not a trusted regular file")
        pointer_raw = os.read(current_fd, 65536)
    finally:
        os.close(current_fd)
    try:
        pointer = json.loads(pointer_raw)
        generation = pointer["generation"]
        lock_digest = pointer["generation_lock_sha256"]
    except (ValueError, KeyError, TypeError) as error:
        fail("vendor/current is malformed")
    if not isinstance(generation, str) or not generation.isalnum() or len(generation) != 12:
        fail("vendor/current generation is invalid")
    if not isinstance(lock_digest, str) or len(lock_digest) != 64:
        fail("vendor/current lock digest is invalid")
    fd = os.open(VENDOR / "generations" / generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if stat.S_IMODE(os.fstat(fd).st_mode) & 0o022:
            fail("generation directory is writable by another user")
        lock_fd = os.open("generation-lock.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            if digest_fd(lock_fd) != lock_digest:
                fail("generation lock digest differs from current pointer")
        finally:
            os.close(lock_fd)
        lock_fd = os.open("generation-lock.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            lock = json.loads(os.read(lock_fd, 1 << 20))
        finally:
            os.close(lock_fd)
        files = lock.get("files")
        new_files = {"pack_and_ask.py", "cdp_lock.py", "LICENSE", "NOTICE", "selectors.json"}
        if not isinstance(files, list):
            fail("generation runtime allowlist is invalid")
        file_keys = set()
        for entry in files:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                fail("generation runtime allowlist is invalid")
            file_keys.add(entry["path"])
        if len(file_keys) != len(files) or file_keys != new_files:
            fail("generation runtime allowlist is invalid")
        expected_files = file_keys
        if set(os.listdir(fd)) != expected_files | {"generation-lock.json"}:
            fail("generation contains unexpected entries")
        for entry in files:
            path, expected = entry.get("path"), entry.get("local_sha256")
            if not isinstance(expected, str) or len(expected) != 64:
                fail("generation file digest is invalid")
            item_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                info = os.fstat(item_fd)
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o022 or digest_fd(item_fd) != expected:
                    fail(f"generation file validation failed: {path}")
            finally:
                os.close(item_fd)
        os.set_inheritable(fd, True)
        return fd
    except BaseException:
        os.close(fd)
        raise


def main() -> None:
    fd = generation_fd()
    # The inherited directory descriptor pins the validated generation across exec.
    target = f"/proc/self/fd/{fd}/pack_and_ask.py"
    # ponytail: 엔진이 cdp_lock을 import하며 세대 디렉터리에 __pycache__를 남기면
    # 다음 실행의 allowlist 검증(os.listdir 정합)이 깨진다 — 바이트코드 캐시 끔.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    os.execve(sys.executable, [sys.executable, target, *sys.argv[1:]], env)


if __name__ == "__main__":
    main()
