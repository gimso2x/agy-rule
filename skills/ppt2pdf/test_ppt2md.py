#!/usr/bin/env python3
"""Offline ppt2md contract checks; no Chrome, model, network, or external files."""

import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "ppt2md.py"
spec = importlib.util.spec_from_file_location("ppt2md", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def make_deck(root: Path, stem: str, count: int) -> Path:
    pdf = root / f"{stem}.pdf"
    pdf.touch()
    for number in range(1, count + 1):
        (root / f"slide-{number:03d}.png").write_bytes(b"png")
    return pdf


def fake_runner_factory(calls, *, fail_at=None, token_count=10):
    def runner(command, timeout):
        calls.append((list(command), timeout))
        assert "--no-tools" in command
        assert "--tools" not in command
        marker = command.index("--")
        seat = os.environ.get("PPT2MD_MODEL", "").strip() or mod.DEFAULT_MODEL
        selector_index = command.index("--model", marker)
        assert command[selector_index + 1] == seat
        attachments = [arg for arg in command[selector_index + 2 : -1] if arg.startswith("@")]
        numbers = [int(re.search(r"slide-(\d{3})\.png$", arg).group(1)) for arg in attachments]
        start, end = numbers[0], numbers[-1]
        if fail_at == start:
            return mod.ChunkResult(1, "", "model failure")
        prompt = command[-1]
        if len(calls) == 1:
            required = (
                "제목",
                "본문 항목",
                "표의 모든 셀",
                "라벨",
                "주석",
                "각주",
                "보이는 텍스트 전부",
                "모든 의미 있는 이미지",
                "다이어그램",
                "UI",
                "그래프",
                "1~2줄 설명",
            )
            assert all(term in prompt for term in required), prompt
        body = "\n".join(
            f"## 슬라이드 {number}\n보존된 본문 {number}\n<!-- PPT2MD_SLIDE_END:{number} -->"
            for number in numbers
        )
        body += f"\n<!-- PPT2MD_CHUNK_END:{start}-{end} -->"
        metadata = {
            "schema_version": 1,
            "provider": seat.split("/", 1)[0],
            "model": seat.split("/", 1)[1],
            "usage": {"input_tokens": token_count, "output_tokens": token_count},
            "cost": 0,
        }
        return mod.ChunkResult(0, body, mod.PROVENANCE_PREFIX + json.dumps(metadata))

    return runner


with tempfile.TemporaryDirectory(prefix="ppt2md-test-") as temp:
    root = Path(temp)
    os.environ["PPT2MD_MODEL"] = "test-provider/test-model"

    # Fixed 5-slide chunks, native attachments, no-tools, prompt contract, and atomic publish.
    pdf = make_deck(root, "report", 6)
    calls = []
    fsync_calls = []
    original_fsync = mod.os.fsync
    mod.os.fsync = lambda fd: (fsync_calls.append(fd), original_fsync(fd))[1]
    try:
        assert mod.convert(pdf, runner=fake_runner_factory(calls)) == 0
    finally:
        mod.os.fsync = original_fsync
    assert len(calls) == 2
    assert [
        [arg for arg in call[0] if arg.startswith("@")]
        for call in calls
    ] == [
        [f"@{root / f'slide-{number:03d}.png'}" for number in range(1, 6)],
        [f"@{root / 'slide-006.png'}"],
    ]
    assert len(fsync_calls) >= 2  # temp file plus parent directory per publish
    assert (root / "report.md").exists()
    assert not list(root.glob(".report.md-*.tmp"))

    # A prior canonical is quarantined before calls and never restored after a later failure.
    failing_pdf = make_deck(root, "failure", 6)
    prior = root / "failure.md"
    prior.write_text("old canonical", encoding="utf-8")
    calls = []
    try:
        mod.convert(failing_pdf, runner=fake_runner_factory(calls, fail_at=6))
    except ValueError:
        pass
    else:
        raise AssertionError("later chunk failure unexpectedly succeeded")
    assert len(calls) == 2
    assert not prior.exists()
    quarantine = root / ".failure.md.quarantine"
    assert quarantine.read_text(encoding="utf-8") == "old canonical"
    assert not list(root.glob(".failure.md-*.tmp"))

    # A stale quarantine from a previous failed run must not block retry:
    # the new run atomically replaces it and publishes on success.
    retry_pdf = make_deck(root, "retry", 6)
    retry_prior = root / "retry.md"
    retry_prior.write_text("old v1", encoding="utf-8")
    (root / ".retry.md.quarantine").write_text("old v0", encoding="utf-8")
    assert mod.convert(retry_pdf, runner=fake_runner_factory([])) == 0
    assert (root / "retry.md").exists()
    assert not (root / ".retry.md.quarantine").exists()
    assert (root / "retry.md").read_text() != "old v1"

    # PDF stems isolate canonical destinations in one parent directory.
    alpha = make_deck(root, "alpha", 1)
    beta = make_deck(root, "beta", 1)
    assert mod.convert(alpha, runner=fake_runner_factory([])) == 0
    assert mod.convert(beta, runner=fake_runner_factory([])) == 0
    assert (root / "alpha.md").exists() and (root / "beta.md").exists()
    assert (root / "alpha.md").read_text() != ""
    assert (root / "beta.md").read_text() != ""

    # 301 slides is rejected before the first model call.
    oversized = root / "oversized"
    oversized.mkdir()
    oversized_pdf = oversized / "oversized.pdf"
    oversized_pdf.touch()
    for number in range(1, 302):
        (oversized / f"slide-{number:03d}.png").write_bytes(b"png")
    calls = []
    try:
        mod.convert(oversized_pdf, runner=fake_runner_factory(calls))
    except ValueError:
        pass
    else:
        raise AssertionError("oversized deck unexpectedly succeeded")
    assert calls == []

    # Reliable cumulative token cap stops before starting the next chunk.
    token_dir = root / "tokens"
    token_dir.mkdir()
    token_pdf = make_deck(token_dir, "tokens", 6)
    calls = []
    try:
        mod.convert(
            token_pdf,
            runner=fake_runner_factory(calls, token_count=500_000),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("token cap unexpectedly permitted the next chunk")
    assert len(calls) == 1
    assert not (token_dir / "tokens.md").exists()

    # Missing captures and gaps fail closed without creating a canonical file.
    bad_dir = root / "bad"
    bad_dir.mkdir()
    bad = bad_dir / "bad.pdf"
    bad.touch()
    (bad_dir / "slide-001.png").touch()
    (bad_dir / "slide-003.png").touch()
    try:
        mod.discover_slides(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("gapped slides unexpectedly accepted")

    # Interleaved headers/end markers must be rejected (body misattribution).
    interleaved = (
        "## 슬라이드 1\n본문1\n## 슬라이드 2\n본문2\n"
        "<!-- PPT2MD_SLIDE_END:1 -->\n<!-- PPT2MD_SLIDE_END:2 -->\n"
        "<!-- PPT2MD_CHUNK_END:1-2 -->"
    )
    try:
        mod.validate_chunk(interleaved, 1, 2)
    except ValueError:
        pass
    else:
        raise AssertionError("interleaved delimiters unexpectedly accepted")

    # A symlink slide capture must be rejected before any transmission.
    link_dir = root / "links"
    link_dir.mkdir()
    link_pdf = make_deck(link_dir, "links", 1)
    outside = root / "outside.png"
    outside.write_bytes(b"png")
    (link_dir / "slide-001.png").unlink()
    os.symlink(outside, link_dir / "slide-001.png")
    try:
        mod.discover_slides(link_pdf)
    except ValueError:
        pass
    else:
        raise AssertionError("symlink slide unexpectedly accepted")

    # Empty capture set after a prior canonical: quarantined (canonical absent),
    # quarantine retained, and no model call happens.
    empty_dir = root / "empty"
    empty_dir.mkdir()
    empty_pdf = empty_dir / "empty.pdf"
    empty_pdf.touch()
    (empty_dir / "empty.md").write_text("stale canonical", encoding="utf-8")
    calls = []
    try:
        mod.convert(empty_pdf, runner=fake_runner_factory(calls))
    except ValueError:
        pass
    else:
        raise AssertionError("empty deck unexpectedly succeeded")
    assert calls == []
    assert not (empty_dir / "empty.md").exists()
    assert (empty_dir / ".empty.md.quarantine").read_text(encoding="utf-8") == "stale canonical"

    # A dangling symlink at the canonical path is still a directory entry: it
    # must be quarantined (lexists semantics) so downstream failure leaves the
    # canonical entry absent and the quarantine retained.
    link_dest_dir = root / "linkdest"
    link_dest_dir.mkdir()
    link_dest_pdf = link_dest_dir / "linkdest.pdf"
    link_dest_pdf.touch()
    os.symlink(link_dest_dir / "nowhere.md", link_dest_dir / "linkdest.md")
    calls = []
    try:
        mod.convert(link_dest_pdf, runner=fake_runner_factory(calls))
    except ValueError:
        pass
    else:
        raise AssertionError("dangling-canonical empty deck unexpectedly succeeded")
    assert calls == []
    assert not (link_dest_dir / "linkdest.md").exists()
    assert not (link_dest_dir / "linkdest.md").is_symlink()
    assert (link_dest_dir / ".linkdest.md.quarantine").is_symlink()

    # The 300-slide boundary is accepted (60 chunks) and the exact effort-suffix
    # contract is enforced: `tiered` is a model id suffix, never stripped.
    assert mod.strip_effort("m:tiered") == "m:tiered"
    assert mod.strip_effort("m:high") == "m"
    big_dir = root / "big"
    big_dir.mkdir()
    big_pdf = make_deck(big_dir, "big", 300)
    calls = []
    assert mod.convert(big_pdf, runner=fake_runner_factory(calls)) == 0
    assert len(calls) == 60
    assert (big_dir / "big.md").exists()

print("PASS (ppt2md offline contracts)")
