#!/usr/bin/env python3
"""Immutable-generation Insane Review control boundary (snapshotted, never run in place)."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path, PurePosixPath
from typing import Any


MAX_PACK_BYTES = 4_194_304
MAX_PACK_TOKENS = 100_000
REQUIRED_MODEL = "GPT-5.6 Sol"
REQUIRED_TIER = "Pro"
TOKENIZER_NAME = "o200k_base"
TOKENIZER_VERSION = "1.0.21"
SELECTOR_KEYS = (
    "model_switcher",
    "model_label_container",
    "prompt_input",
    "prompt_input_fallback",
    "file_upload_input",
    "file_upload_input_fallback",
    "attachment_pill",
    "assistant_turn",
    "stop_button",
    "login_button",
    "copy_button",
    "duplicate_modal",
)
_last_tokenizer_version: str | None = None


def die(s: str) -> None:
    raise RuntimeError(s)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return digest_bytes(f.read())


def ancestors_safe(path: Path) -> None:
    for parent in reversed((path, *path.parents)):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            die(f"unsafe ancestor: {parent}")


def root(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    ancestors_safe(path)
    if stat.S_IMODE(path.stat().st_mode) != 0o700:
        die("private root must be 0700")
    return path


def directory_fd(path: Path) -> int:
    path = path.absolute()
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=fd,
            )
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def private_write(root_path: Path, suffix: str, payload: bytes) -> Path:
    root(root_path)
    name = f"{time.time_ns()}-{uuid.uuid4().hex}{suffix}"
    path = root_path / name
    parent_fd = directory_fd(root_path)
    try:
        fd = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o600,
            dir_fd=parent_fd,
        )
    finally:
        os.close(parent_fd)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def load_selectors() -> dict[str, Any]:
    """Load the signed-generation selector map from beside this engine."""
    path = Path(__file__).absolute().parent / "selectors.json"
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            die("selectors.json must be a regular file")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            raw = os.read(fd, MAX_PACK_BYTES + 1)
        finally:
            os.close(fd)
        data = json.loads(raw.decode("utf-8"))
    except RuntimeError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        raise RuntimeError("selectors.json is invalid") from error
    if not isinstance(data, dict) or data.get("schema") != 1:
        die("selectors schema must be 1")
    if set(data) != {"schema", *SELECTOR_KEYS}:
        die("selectors keys are invalid")
    result: dict[str, Any] = {}
    for key in SELECTOR_KEYS:
        value = data[key]
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, list):
            candidates = value
        else:
            die(f"selector {key} must be a string or string array")
        if not candidates or any(not isinstance(item, str) or not item.strip() for item in candidates):
            die(f"selector {key} must contain nonempty strings")
        result[key] = candidates
    return result


def canonical(v: str) -> str:
    if not isinstance(v, str):
        die("invalid manifest path")
    p = PurePosixPath(v)
    if not v or p.is_absolute() or ".." in p.parts or str(p) != v:
        die("invalid manifest path")
    return v


def manifest(path: Path) -> list[dict[str, str]]:
    try:
        data = json.loads(path.read_text())
        files = data["files"] if isinstance(data, dict) else data
    except Exception as error:
        raise RuntimeError("malformed manifest") from error
    if not isinstance(files, list) or not files:
        die("manifest must be nonempty")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            die("invalid manifest entry")
        name, digest = canonical(item["path"]), item["sha256"]
        if (
            name in seen
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            die("invalid manifest digest")
        seen.add(name)
        out.append({"path": name, "sha256": digest})
    return sorted(out, key=lambda x: x["path"])


def secure_source(repo: Path, relative: str) -> Path:
    ancestors_safe(repo)
    path = repo
    for part in PurePosixPath(relative).parts:
        path = path / part
        try:
            info = path.lstat()
        except OSError as error:
            raise RuntimeError(f"missing source: {relative}") from error
        if stat.S_ISLNK(info.st_mode):
            die(f"symlinked source: {relative}")
    if not path.is_file():
        die(f"missing source: {relative}")
    return path


def secretlint(repo: Path, config: Path, files: list[str]) -> dict[str, Any]:
    if not config.is_file() or config.is_symlink():
        die("secretlint configuration is required")
    try:
        config_data = json.loads(config.read_text())
    except (OSError, ValueError) as error:
        raise RuntimeError("secretlint configuration must be JSON") from error
    if not isinstance(config_data, dict) or any(
        key in config_data for key in ("ignore", "ignores", "ignorePatterns")
    ):
        die("secretlint ignore rules are forbidden for required files")
    with tempfile.NamedTemporaryFile(
        mode="w", prefix="mygjc-secretlint-ignore-", delete=True
    ) as ignore:
        ignore.flush()
        absolute_files = [str(repo / path) for path in files]
        try:
            result = subprocess.run(
                [
                    "secretlint",
                    "--format",
                    "json",
                    "--secretlintrc",
                    str(config),
                    "--secretlintignore",
                    ignore.name,
                    *absolute_files,
                ],
                cwd=repo.anchor,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError("secretlint mandatory and unavailable") from error
    evidence = {
        "exit_code": result.returncode,
        "stdout_sha256": digest_bytes(result.stdout.encode()),
        "stderr_sha256": digest_bytes(result.stderr.encode()),
        "excluded": [],
        "scanned_files": sorted(files),
    }
    try:
        parsed = json.loads(result.stdout) if result.stdout.strip() else []
    except ValueError as error:
        raise RuntimeError("secretlint returned non-JSON evidence") from error
    if not isinstance(parsed, (list, dict)) or result.returncode:
        die("secretlint rejected transfer")
    if set(evidence["excluded"]) & set(files):
        die("required manifest file excluded by secretlint")
    return evidence


_TOKENIZER_SCRIPT = r"""
const fs = require("node:fs");
const path = require("node:path");
const rankModule = require("js-tiktoken/ranks/o200k_base");
const ranks = rankModule.default ?? rankModule;
const { Tiktoken } = require("js-tiktoken/lite");
function packageJson() {
  let dir = path.dirname(require.resolve("js-tiktoken"));
  for (;;) {
    const candidate = path.join(dir, "package.json");
    try {
      const value = JSON.parse(fs.readFileSync(candidate, "utf8"));
      if (value.name === "js-tiktoken") return value;
    } catch (_) {}
    const parent = path.dirname(dir);
    if (parent === dir) throw new Error("js-tiktoken package root not found");
    dir = parent;
  }
}
const version = packageJson().version;
if (process.argv[1] === "--probe") {
  process.stdout.write(JSON.stringify({version}) + "\n");
} else {
  const enc = new Tiktoken(ranks);
  const chunks = [];
  process.stdin.on("data", chunk => chunks.push(chunk));
  process.stdin.on("end", () => {
    const text = Buffer.concat(chunks).toString("utf8");
    const tokens = enc.encode(text).length;
    process.stdout.write(JSON.stringify({tokens, version}) + "\n");
  });
}
"""


def node_env() -> dict[str, str]:
    env = os.environ.copy()
    try:
        npm_root = subprocess.run(
            ["npm", "root", "-g"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        npm_root = ""
    if npm_root and not env.get("NODE_PATH"):
        env["NODE_PATH"] = npm_root
    return env


def _tokenizer_probe() -> tuple[bool, str | None, str | None]:
    if not shutil.which("node"):
        return False, None, "node unavailable"
    try:
        result = subprocess.run(
            ["node", "-e", _TOKENIZER_SCRIPT, "--", "--probe"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            env=node_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, None, str(error)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode or len(lines) != 1:
        return False, None, "tokenizer probe failed"
    try:
        observed = json.loads(lines[0])
    except ValueError:
        return False, None, "tokenizer probe returned malformed JSON"
    version = observed.get("version") if isinstance(observed, dict) else None
    if not isinstance(version, str) or not version:
        return False, None, "tokenizer version missing"
    return True, version, None


def _canonical_text(pack: Path) -> str:
    members: list[tuple[str, bytes]] = []
    try:
        with tarfile.open(pack, "r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    die("pack contains non-regular entry")
                path = canonical(member.name)
                payload = archive.extractfile(member)
                if payload is None:
                    die("pack parse failed")
                members.append((path, payload.read()))
    except (tarfile.TarError, OSError) as error:
        raise RuntimeError("pack parse failed") from error
    if not members:
        die("pack must contain a regular member")
    members.sort(key=lambda item: item[0])
    if len({path for path, _ in members}) != len(members):
        die("pack contains duplicate path")
    chunks: list[str] = []
    for path, payload in members:
        try:
            content = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise RuntimeError(f"pack member is not UTF-8: {path}") from error
        chunks.append(f"--- FILE: {path} ---\n{content}\n")
    return "".join(chunks)


def _measure_tokens(pack: Path) -> tuple[int, str]:
    try:
        pack_bytes = pack.stat().st_size
    except OSError as error:
        raise RuntimeError("pack parse failed") from error
    if pack_bytes == 0 or pack_bytes > MAX_PACK_BYTES:
        die("pack byte limit")
    canonical_text = _canonical_text(pack)
    try:
        result = subprocess.run(
            ["node", "-e", _TOKENIZER_SCRIPT],
            input=canonical_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            env=node_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("tokenizer execution failed") from error
    try:
        raw_output = (
            result.stdout
            if isinstance(result.stdout, bytes)
            else str(result.stdout).encode("utf-8")
        )
        output = raw_output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError("tokenizer returned non-UTF-8 output") from error
    lines = [line for line in output.splitlines() if line.strip()]
    if result.returncode or len(lines) != 1:
        die("tokenizer returned invalid output")
    try:
        observed = json.loads(lines[0])
    except ValueError as error:
        raise RuntimeError("tokenizer returned malformed JSON") from error
    if not isinstance(observed, dict) or set(observed) != {"tokens", "version"}:
        die("tokenizer returned malformed JSON")
    tokens, version = observed["tokens"], observed["version"]
    if type(tokens) is not int or tokens < 0:
        die("tokenizer returned invalid token count")
    if not isinstance(version, str) or not version:
        die("tokenizer returned invalid version")
    if version != TOKENIZER_VERSION:
        die(f"unsupported tokenizer version: {version}")
    return tokens, version


def token_count(pack: Path) -> int:
    global _last_tokenizer_version
    tokens, version = _measure_tokens(pack)
    _last_tokenizer_version = version
    return tokens


def packed_manifest(pack: Path) -> list[dict[str, str]]:
    try:
        with tarfile.open(pack) as archive:
            out: list[dict[str, str]] = []
            for member in archive.getmembers():
                if not member.isfile():
                    die("pack contains non-regular entry")
                payload = archive.extractfile(member)
                if payload is None:
                    die("pack parse failed")
                out.append({"path": canonical(member.name), "sha256": digest_bytes(payload.read())})
            return sorted(out, key=lambda x: x["path"])
    except (tarfile.TarError, OSError) as error:
        raise RuntimeError("pack parse failed") from error


def _validated_run_id(value: str | None) -> str:
    if value is None:
        return str(uuid.uuid4())
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError):
        die("run_id must be a UUID")
    if str(parsed) != value.lower():
        die("run_id must be a canonical UUID")
    return value


def journal_append(root_path: Path, event_dict: dict[str, Any]) -> None:
    if not isinstance(event_dict, dict):
        die("journal event must be an object")
    output = root(root_path)
    try:
        line = (
            json.dumps(event_dict, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise RuntimeError("journal event is not JSON") from error
    parent_fd = directory_fd(output)
    fd: int | None = None
    locked = False
    try:
        try:
            fd = os.open(
                "journal.jsonl",
                os.O_WRONLY
                | os.O_APPEND
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                0o600,
                dir_fd=parent_fd,
            )
        except FileExistsError:
            info = os.stat("journal.jsonl", dir_fd=parent_fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                die("journal symlink is forbidden")
            fd = os.open(
                "journal.jsonl",
                os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            die("unsafe journal")
        fcntl.flock(fd, fcntl.LOCK_EX)
        locked = True
        written = os.write(fd, line)
        if written != len(line):
            die("journal write incomplete")
        os.fsync(fd)
    except OSError as error:
        raise RuntimeError("journal append failed") from error
    finally:
        if fd is not None:
            if locked:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(fd)
        os.close(parent_fd)


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    selectors = load_selectors()
    del selectors
    repo = Path(args.repo).absolute()
    intended = manifest(Path(args.intended).absolute())
    run_id = _validated_run_id(getattr(args, "run_id", None))
    sources: list[Path] = []
    for item in intended:
        path = secure_source(repo, item["path"])
        if sha256(path) != item["sha256"]:
            die("source manifest drift")
        sources.append(path)
    lint = secretlint(
        repo, Path(args.secretlint_config).absolute(), [item["path"] for item in intended]
    )
    output = root(Path(args.artifact_root).absolute())
    fd, temporary = tempfile.mkstemp(dir=output, prefix="staging-", suffix=".tar")
    os.close(fd)
    staging = Path(temporary)
    try:
        os.chmod(staging, 0o600)
        with tarfile.open(staging, "w") as archive:
            for item, path in zip(intended, sources):
                archive.add(path, arcname=item["path"], recursive=False)
        actual = packed_manifest(staging)
        if actual != intended:
            die("intended and actual manifest differ")
        if staging.stat().st_size == 0 or staging.stat().st_size > MAX_PACK_BYTES:
            die("pack byte limit")
        tokens = token_count(staging)
        tokenizer_version = _last_tokenizer_version
        if tokenizer_version != TOKENIZER_VERSION:
            die("tokenizer version unavailable")
        if tokens > MAX_PACK_TOKENS:
            die("pack token limit")
        actual_path = private_write(
            output,
            ".actual-manifest.json",
            json.dumps({"files": actual}, sort_keys=True, separators=(",", ":")).encode(),
        )
        intended_path = private_write(
            output,
            ".intended-manifest.json",
            json.dumps({"files": intended}, sort_keys=True, separators=(",", ":")).encode(),
        )
        pack = private_write(output, ".pack.tar", staging.read_bytes())
    finally:
        staging.unlink(missing_ok=True)
    pack_digest = sha256(pack)
    manifest_digest = sha256(actual_path)
    receipt = {
        "pack": str(pack),
        "pack_sha256": pack_digest,
        "manifest": str(actual_path),
        "manifest_sha256": manifest_digest,
        "intended_manifest": str(intended_path),
        "bytes": pack.stat().st_size,
        "tokens": tokens,
        "tokenizer": TOKENIZER_NAME,
        "tokenizer_version": tokenizer_version,
        "run_id": run_id,
        "secretlint": lint,
    }
    receipt_path = private_write(output, ".prepare.json", json.dumps(receipt, sort_keys=True).encode())
    journal_append(
        output,
        {
            "ts": time.time(),
            "op": "prepare",
            "run_id": run_id,
            "manifest_sha": manifest_digest,
            "pack_sha": pack_digest,
            "tokens": tokens,
            "bytes": pack.stat().st_size,
        },
    )
    receipt["receipt"] = str(receipt_path)
    return receipt


def open_private(path: Path, expected: str) -> int:
    path = path.absolute()
    parts = path.parts
    parent_fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in parts[1:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            os.close(parent_fd)
            parent_fd = next_fd
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_fd)
    except OSError as error:
        raise RuntimeError("unsafe private artifact") from error
    finally:
        os.close(parent_fd)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
        os.close(fd)
        die("unsafe private artifact")
    data = os.read(fd, info.st_size)
    os.lseek(fd, 0, os.SEEK_SET)
    if not data or len(data) > MAX_PACK_BYTES or digest_bytes(data) != expected:
        os.close(fd)
        die("artifact identity changed")
    return fd


def fd_digest(fd: int) -> str:
    position = os.lseek(fd, 0, os.SEEK_CUR)
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 1 << 20)
        if not chunk:
            break
        chunks.append(chunk)
    os.lseek(fd, position, os.SEEK_SET)
    return digest_bytes(b"".join(chunks))


def endpoint(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
        die("localhost CDP required")
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/json/version", timeout=5) as response:
            data = json.load(response)
    except Exception as error:
        raise RuntimeError("CDP unavailable") from error
    if not isinstance(data.get("webSocketDebuggerUrl"), str):
        die("invalid CDP")
    return url


def profile(path: Path) -> None:
    ancestors_safe(path.parent)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        die("unsafe dedicated profile")


def profile_bound(endpoint_url: str, profile_dir: Path) -> int:
    port = urllib.parse.urlparse(endpoint_url).port
    try:
        processes = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("cannot verify CDP profile binding") from error
    expected = f"--user-data-dir={profile_dir}"
    for line in processes:
        if (
            (f"--remote-debugging-port={port}" in line or f"--remote-debugging-port {port}" in line)
            and expected in line
        ):
            return int(line.strip().split(maxsplit=1)[0])
    die("CDP endpoint is not bound to the dedicated profile")


def listener_owned(pid: int, port: int) -> None:
    socket_inodes: set[str] = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            for line in Path(table).read_text().splitlines()[1:]:
                fields = line.split()
                if int(fields[1].rsplit(":", 1)[1], 16) == port and fields[3] == "0A":
                    socket_inodes.add(fields[9])
        except (OSError, ValueError, IndexError):
            continue
    try:
        links = [
            item.readlink().name
            for item in (Path("/proc") / str(pid) / "fd").iterdir()
            if item.is_symlink()
        ]
    except OSError as error:
        raise RuntimeError("cannot verify CDP listener owner") from error
    if not any(link.startswith("socket:[") and link[8:-1] in socket_inodes for link in links):
        die("dedicated browser does not own the CDP listener")


def upload(
    fd: int, endpoint_url: str, prompt: str, timeout: int, profile_dir: Path
) -> str:
    selectors = load_selectors()
    script = r"""
const {chromium}=require("playwright");
const fs=require("fs");
const x=JSON.parse(fs.readFileSync(0,"utf8"));
const list=v=>Array.isArray(v)?v:[v];
async function first(page, candidates, state="visible") {
  for (const selector of list(candidates)) {
    try {
      const locator=page.locator(selector).first();
      await locator.waitFor({state,timeout:Math.min(2500,x.timeout)});
      return locator;
    } catch (_) {}
  }
  throw Error("selector unavailable");
}
async function count(page, candidates) {
  for (const selector of list(candidates)) {
    const locator=page.locator(selector);
    const value=await locator.count();
    for (let i=0;i<value;i++) {
      if (await locator.nth(i).isVisible().catch(()=>false)) return {selector,count:value};
    }
  }
  return {selector:null,count:0};
}
async function exactModel(page) {
  for (const selector of list(x.selectors.model_label_container)) {
    const labels=page.locator(selector);
    const total=await labels.count();
    for (let i=0;i<total;i++) {
      const label=labels.nth(i);
      if (!(await label.isVisible().catch(()=>false))) continue;
      const texts=[await label.innerText().catch(()=>""),...(await label.locator("*").allTextContents().catch(()=>[]))];
      if (texts.some(text=>text.trim()===x.model || text.split(/\r?\n/).some(line=>line.trim()===x.model))) return true;
    }
  }
  return false;
}
async function readClipboard(page) {
  try { return await page.evaluate(()=>navigator.clipboard.readText()); }
  catch (_) { return null; }
}
(async()=>{
  const browser=await chromium.connectOverCDP(x.endpoint);
  try {
    const context=browser.contexts().find(c=>c.pages().some(p=>p.url().includes("chatgpt.com")));
    if (!context) throw Error("manual login unavailable");
    const page=context.pages().find(p=>p.url().includes("chatgpt.com"));
    if (!page) throw Error("manual login unavailable");
    const login=await count(page,x.selectors.login_button);
    if (login.count) throw Error("manual login unavailable");
    const model=await first(page,x.selectors.model_switcher);
    await model.click();
    try {
      if (!(await exactModel(page))) throw Error("exact model unavailable");
    } finally {
      await page.keyboard.press("Escape").catch(()=>{});
    }
    const beforeTurns=await page.locator(list(x.selectors.assistant_turn).join(",")).count();
    const attachments=page.locator(list(x.selectors.attachment_pill).join(","));
    const attachmentBefore=await attachments.count();
    let input;
    try { input=await first(page,x.selectors.file_upload_input,"attached"); }
    catch (_) { input=await first(page,x.selectors.file_upload_input_fallback,"attached"); }
    await input.setInputFiles({name:x.packName,mimeType:"application/x-tar",buffer:fs.readFileSync(x.pack)});
    const duplicate=await count(page,x.selectors.duplicate_modal);
    if (duplicate.count) {
      const modal=page.locator(duplicate.selector).first();
      let confirm=modal.getByRole("button",{name:/확인|confirm|continue|replace|upload/i}).first();
      if (!(await confirm.count())) confirm=modal.locator("button").last();
      await confirm.waitFor({state:"visible",timeout:x.timeout});
      await confirm.click();
    }
    const pill=attachments.nth(attachmentBefore);
    await pill.waitFor({state:"visible",timeout:x.timeout});
    if (!(await pill.innerText()).includes(x.packName)) throw Error("approved attachment name mismatch");
    let box;
    try { box=await first(page,x.selectors.prompt_input); }
    catch (_) { box=await first(page,x.selectors.prompt_input_fallback); }
    await box.fill(x.prompt);
    await box.press("Enter");
    const stop=await first(page,x.selectors.stop_button);
    const turn=page.locator(list(x.selectors.assistant_turn).join(",")).nth(beforeTurns);
    await turn.waitFor({state:"visible",timeout:x.timeout});
    await stop.waitFor({state:"hidden",timeout:x.timeout});
    let response=null;
    let capture_method="innerText";
    const beforeClipboard=await readClipboard(page);
    const copy=await count(turn,x.selectors.copy_button);
    if (copy.count) {
      try {
        await turn.locator(copy.selector).first().click();
        for (let i=0;i<30;i++) {
          await new Promise(resolve=>setTimeout(resolve,100));
          const afterClipboard=await readClipboard(page);
          if (typeof afterClipboard==="string" && afterClipboard.trim() && afterClipboard!==beforeClipboard) {
            response=afterClipboard.trim();
            capture_method="clipboard";
            break;
          }
        }
      } catch (_) {}
    }
    if (!response) response=(await turn.innerText()).trim();
    if (!response || response===x.prompt || /sign in|log in|access denied/i.test(response)) {
      throw Error("invalid assistant turn");
    }
    process.stdout.write(JSON.stringify({response,capture_method})+"\n");
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error.message);process.exit(1)});
"""
    payload = json.dumps(
        {
            "endpoint": endpoint_url,
            "pack": f"/proc/self/fd/{fd}",
            "packName": f"mygjc-{fd_digest(fd)[:16]}.tar",
            "prompt": prompt,
            "timeout": timeout * 1000,
            "model": REQUIRED_MODEL,
            "tier": REQUIRED_TIER,
            "selectors": selectors,
            "profile": str(profile_dir),
        }
    )
    try:
        result = subprocess.run(
            ["node", "-e", script],
            input=payload,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 15,
            pass_fds=(fd,),
            env=node_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("CDP model/attachment/assistant completion failed") from error
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode or len(lines) != 1:
        die("CDP model/attachment/assistant completion failed")
    try:
        captured = json.loads(lines[0])
    except ValueError as error:
        raise RuntimeError("assistant capture returned malformed JSON") from error
    if (
        not isinstance(captured, dict)
        or set(captured) != {"response", "capture_method"}
        or not isinstance(captured["response"], str)
        or captured["capture_method"] not in {"clipboard", "innerText"}
    ):
        die("assistant capture returned invalid JSON")
    return captured["response"]


def failure_receipt(out: Path, stage: str, error: BaseException, run_id: str) -> Path:
    # Never retain prompt, source, cookie, or response content in a failure receipt.
    return private_write(
        out,
        ".failure.json",
        json.dumps(
            {"stage": stage, "error": str(error)[:256], "run_id": run_id},
            sort_keys=True,
        ).encode(),
    )


def send(args: argparse.Namespace) -> dict[str, Any]:
    output = root(Path(args.artifact_root).absolute())
    run_id = _validated_run_id(getattr(args, "run_id", None))
    manifest_fd: int | None = None
    pack_fd: int | None = None
    started = time.monotonic()
    stage = "validation"
    approval_path: Path | None = None
    response_path: Path | None = None
    success_path: Path | None = None
    try:
        profile_path = Path(args.profile_dir).absolute()
        profile(profile_path)
        manifest_fd = open_private(Path(args.manifest).absolute(), args.approved_manifest_sha)
        pack_fd = open_private(Path(args.pack).absolute(), args.approved_pack_sha)
        if packed_manifest(Path(f"/proc/self/fd/{pack_fd}")) != manifest(Path(f"/proc/self/fd/{manifest_fd}")):
            die("approved manifest differs from pack")
        from cdp_lock import CdpLease

        verified_endpoint = endpoint(args.cdp_endpoint)
        browser_pid = profile_bound(verified_endpoint, profile_path)
        listener_owned(browser_pid, urllib.parse.urlparse(verified_endpoint).port or 0)
        approval_path = private_write(
            output,
            ".approval.json",
            json.dumps(
                {
                    "pack_sha256": args.approved_pack_sha,
                    "manifest_sha256": args.approved_manifest_sha,
                    "model": f"{REQUIRED_MODEL} {REQUIRED_TIER}",
                    "endpoint": verified_endpoint,
                    "browser_pid": browser_pid,
                    "run_id": run_id,
                },
                sort_keys=True,
            ).encode(),
        )
        stage = "external-send"
        with CdpLease(output, urllib.parse.urlparse(verified_endpoint).port or 0):
            response = upload(pack_fd, verified_endpoint, args.prompt, args.timeout, profile_path)
        stage = "post-upload-persistence"
        response_path = private_write(output, ".response.md", response.encode("utf-8"))
        stage = "response-journal"
        journal_append(
            output,
            {
                "ts": time.time(),
                "op": "response_persisted",
                "run_id": run_id,
                "response": str(response_path),
                "response_sha": sha256(response_path),
                "pack_sha": args.approved_pack_sha,
                "manifest_sha": args.approved_manifest_sha,
            },
        )
        stage = "success-receipt"
        success_path = private_write(
            output,
            ".send-success.json",
            json.dumps(
                {
                    "approval": str(approval_path),
                    "response": str(response_path),
                    "pack_sha256": args.approved_pack_sha,
                    "manifest_sha256": args.approved_manifest_sha,
                    "run_id": run_id,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                },
                sort_keys=True,
            ).encode(),
        )
    except BaseException as error:
        try:
            failure_receipt(output, stage, error, run_id)
        except BaseException:
            pass
        try:
            journal_append(
                output,
                {"ts": time.time(), "op": "send_failed", "run_id": run_id, "stage": stage},
            )
        except BaseException:
            pass
        raise
    finally:
        if manifest_fd is not None:
            os.close(manifest_fd)
        if pack_fd is not None:
            os.close(pack_fd)
    if response_path is None or success_path is None or approval_path is None:
        die("send did not produce required receipts")
    return {
        "response": str(response_path),
        "success_receipt": str(success_path),
        "approval_receipt": str(approval_path),
        "pack_sha256": args.approved_pack_sha,
        "manifest_sha256": args.approved_manifest_sha,
        "run_id": run_id,
        "model": f"{REQUIRED_MODEL} {REQUIRED_TIER}",
    }


def check_env(args: argparse.Namespace) -> dict[str, Any]:
    selectors_state = "ready"
    try:
        selectors = load_selectors()
    except RuntimeError as error:
        selectors = None
        selectors_state = f"invalid: {error}"
    tokenizer_available, tokenizer_version, tokenizer_reason = _tokenizer_probe()
    state: dict[str, Any] = {
        "python": sys.version.split()[0],
        "secretlint": bool(shutil.which("secretlint")),
        "node": bool(shutil.which("node")),
        "playwright": False,
        "tokenizer": {
            "available": tokenizer_available,
            "version": tokenizer_version,
            "reason": tokenizer_reason,
        },
        "selectors": selectors_state,
        "cdp": "unobserved",
        "profile": "unobserved",
        "login": "unobserved",
        "model": "unobserved",
        "reason": None,
        "ready": False,
    }
    if not state["node"] or selectors is None:
        return state
    state["playwright"] = (
        subprocess.run(
            ["node", "-e", "require.resolve('playwright')"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=node_env(),
            check=False,
        ).returncode
        == 0
    )
    if getattr(args, "cdp_endpoint", None) and getattr(args, "profile_dir", None):
        try:
            profile_path = Path(args.profile_dir).absolute()
            profile(profile_path)
            state["profile"] = "valid"
            verified_endpoint = endpoint(args.cdp_endpoint)
            profile_bound(verified_endpoint, profile_path)
            state["cdp"] = "reachable"
            probe = r"""
const {chromium}=require("playwright");
const fs=require("fs");
const x=JSON.parse(fs.readFileSync(0,"utf8"));
const list=v=>Array.isArray(v)?v:[v];
async function find(page,candidates) {
  for (const selector of list(candidates)) {
    const locator=page.locator(selector).first();
    if (await locator.count() && await locator.isVisible().catch(()=>false)) return locator;
  }
  return null;
}
async function exactModel(page) {
  for (const selector of list(x.selectors.model_label_container)) {
    const labels=page.locator(selector);
    for (let i=0;i<await labels.count();i++) {
      const label=labels.nth(i);
      if (!(await label.isVisible().catch(()=>false))) continue;
      const texts=[await label.innerText().catch(()=>""),...(await label.locator("*").allTextContents().catch(()=>[]))];
      if (texts.some(text=>text.trim()===x.model || text.split(/\r?\n/).some(line=>line.trim()===x.model))) return true;
    }
  }
  return false;
}
(async()=>{
  const browser=await chromium.connectOverCDP(x.endpoint);
  try {
    const page=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes("chatgpt.com"));
    if (!page) { console.log(JSON.stringify({login:"missing",model:"unobserved",reason:"no_chatgpt_page"})); return; }
    const login=await find(page,x.selectors.login_button);
    const prompt=await find(page,x.selectors.prompt_input)||await find(page,x.selectors.prompt_input_fallback);
    if (login||!prompt) { console.log(JSON.stringify({login:"missing",model:"unobserved",reason:"authentication_required"})); return; }
    const model=await find(page,x.selectors.model_switcher);
    if (!model) { console.log(JSON.stringify({login:"ready",model:"unobservable",reason:"model_selector_unavailable"})); return; }
    await model.click();
    let matched=false;
    try { matched=await exactModel(page); }
    finally { await page.keyboard.press("Escape").catch(()=>{}); }
    console.log(JSON.stringify({login:"ready",model:matched?"ready":"mismatch",reason:matched?null:"model_mismatch"}));
  } finally { await browser.close(); }
})().catch(error=>{console.log(JSON.stringify({login:"unobservable",model:"unobservable",reason:"probe_error:"+error.message}));});
"""
            probe_result = subprocess.run(
                ["node", "-e", probe],
                input=json.dumps(
                    {
                        "endpoint": verified_endpoint,
                        "model": REQUIRED_MODEL,
                        "selectors": selectors,
                    }
                ),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                env=node_env(),
                check=False,
            )
            if probe_result.returncode == 0:
                lines = [line for line in probe_result.stdout.splitlines() if line.strip()]
                observed = None
                for line in reversed(lines):
                    try:
                        observed = json.loads(line)
                        break
                    except ValueError:
                        continue
                if not isinstance(observed, dict):
                    raise ValueError("missing probe JSON")
                state.update(
                    login=observed["login"],
                    model=observed["model"],
                    reason=observed["reason"],
                )
                state["ready"] = bool(
                    state["secretlint"]
                    and state["playwright"]
                    and state["tokenizer"]["available"]
                    and state["tokenizer"]["version"] == TOKENIZER_VERSION
                    and state["selectors"] == "ready"
                    and state["login"] == "ready"
                    and state["model"] == "ready"
                )
            else:
                state["reason"] = "probe_process_failed"
        except RuntimeError as error:
            state["reason"] = str(error)
        except (subprocess.SubprocessError, ValueError, KeyError):
            state["reason"] = "probe_unparseable"
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    for option in ("--repo", "--intended", "--secretlint-config"):
        prepare_parser.add_argument(option, required=True)
    prepare_parser.add_argument("--run-id")
    prepare_parser.add_argument("--artifact-root", default=".insane-review")
    send_parser = subparsers.add_parser("send")
    for option in (
        "--pack",
        "--manifest",
        "--approved-pack-sha",
        "--approved-manifest-sha",
        "--cdp-endpoint",
        "--profile-dir",
        "--prompt",
    ):
        send_parser.add_argument(option, required=True)
    send_parser.add_argument("--run-id", required=True)
    send_parser.add_argument("--timeout", type=int, default=120)
    send_parser.add_argument("--artifact-root", default=".insane-review")
    env_parser = subparsers.add_parser("check-env")
    env_parser.add_argument("--cdp-endpoint")
    env_parser.add_argument("--profile-dir")
    args = parser.parse_args()
    try:
        value = (
            prepare(args)
            if args.cmd == "prepare"
            else send(args)
            if args.cmd == "send"
            else check_env(args)
        )
        print(json.dumps(value, sort_keys=True))
        return 0
    except RuntimeError as error:
        print(f"insane-review: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
