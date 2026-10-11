#!/usr/bin/env python3
"""Convert captured PowerPoint slide PNGs into a complete Markdown document."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "bin" / "wiki-print-once.py"
DEFAULT_MODEL = "gimso2xproxy/gemini-3.8-flash-tiered"
PROVENANCE_PREFIX = "GJC_PRINT_ONCE_META_V1="
META_PREFIX = "PPT2MD_META_V1="
SLIDE_RE = re.compile(r"^slide-(\d{3})\.png$")
HEADER_RE = re.compile(r"^## 슬라이드 (\d+)$", re.MULTILINE)

MAX_SLIDES = 300
MAX_CHUNKS = 60
CHUNK_SIZE = 5
CHUNK_TIMEOUT = 300.0
TOTAL_TIMEOUT = 3600.0
MAX_TOKENS = 1_000_000
MD_FAILURE = 2
EFFORT_SUFFIXES = {"minimal", "low", "medium", "high", "xhigh", "max"}
# ponytail: approved contract limits removable effort suffixes to the six above;
# `tiered` is a distinct model id suffix and must never be stripped.


class ChunkResult:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


Runner = Callable[[Sequence[str], float], ChunkResult]


def resolve_pdf(path: Path) -> Path:
    if path.is_dir():
        candidates = sorted(path.glob("*.pdf"))
        if len(candidates) != 1:
            raise ValueError("deck directory must contain exactly one PDF")
        path = candidates[0]
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError("input must be a completed PDF path")
    return path.resolve()


def discover_slides(pdf_path: Path) -> list[Path]:
    candidates = sorted(pdf_path.parent.glob("slide-*.png"))
    if not candidates:
        raise ValueError("no slide-*.png captures found beside PDF")
    slides: dict[int, Path] = {}
    for path in candidates:
        match = SLIDE_RE.fullmatch(path.name)
        if match is None:
            raise ValueError(f"invalid slide filename: {path.name}")
        number = int(match.group(1))
        if number in slides:
            raise ValueError(f"duplicate slide number: {number}")
        # ponytail: a symlink/non-regular slide could transmit an arbitrary
        # outside image to the external model — reject before any transmission.
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"slide capture must be a regular file: {path.name}")
        if path.resolve().parent != pdf_path.parent:
            raise ValueError(f"slide capture escapes the deck directory: {path.name}")
        slides[number] = path
    expected = set(range(1, len(slides) + 1))
    if set(slides) != expected:
        raise ValueError("slide captures must be a contiguous slide-001..slide-NNN set")
    return [slides[number] for number in sorted(slides)]


def destination(pdf_path: Path) -> Path:
    return pdf_path.with_suffix(".md")


def quarantine_prior(dest: Path) -> Path | None:
    # ponytail: lexists semantics — a dangling symlink at the canonical path is
    # still a directory entry that must be quarantined (Path.exists() follows
    # symlinks and would treat it as absent).
    if not dest.exists() and not dest.is_symlink():
        return None
    quarantine = dest.with_name(f".{dest.stem}.md.quarantine")
    # ponytail: os.replace overwrites atomically — a quarantine left by a
    # previous failed run is itself a superseded md, so a new run replaces it
    # instead of hard-blocking retry. Fail-closed semantics are preserved:
    # canonical is moved away before any model call and stays absent on failure.
    os.replace(dest, quarantine)
    return quarantine


def prompt_for(slides: Sequence[Path], start: int, end: int) -> str:
    # ponytail: attachments are passed as separate @-argv outside the prompt;
    # the prompt references slides only by ordinal so a hostile deck folder name
    # can never inject model instructions or leak local paths.
    return f"""You are converting a captured presentation to Markdown. The attached images are exactly slides {start}-{end}, in order (slide {start} is the first attached image, slide {end} the last).

For EVERY attached slide, preserve the full visible content, not a summary or omission:
- Copy the title, every body item, every table cell, labels, annotations, footnotes, and all other visible text in full (제목, 본문 항목, 표의 모든 셀, 라벨, 주석, 각주를 포함한 보이는 텍스트 전부).
- For every meaningful image, diagram, UI, and graph, write a clear 1-2 line caption describing its content and relationships (모든 의미 있는 이미지/다이어그램/UI/그래프마다 내용과 관계를 설명하는 1~2줄 설명).

Use exactly one heading `## 슬라이드 N` per slide, in order. Do not invent unseen text. End each slide with exactly `<!-- PPT2MD_SLIDE_END:N -->`. After the final slide, end the chunk with exactly `<!-- PPT2MD_CHUNK_END:{start}-{end} -->`. The final delimiters must be present even when a slide is visually sparse. Your response must END with that chunk-end marker: no trailing text, commentary, code fences, or whitespace after it — the last characters of your response are exactly `<!-- PPT2MD_CHUNK_END:{start}-{end} -->`."""


def run_helper(command: Sequence[str], timeout: float) -> ChunkResult:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=max(timeout + 5.0, 10.0),
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return ChunkResult(124, error.stdout or "", error.stderr or "")
    except OSError as error:
        return ChunkResult(127, "", str(error))
    return ChunkResult(result.returncode, result.stdout, result.stderr)


def parse_helper_meta(stderr: str) -> dict[str, object]:
    latest: dict[str, object] = {}
    for line in stderr.splitlines():
        if not line.startswith(PROVENANCE_PREFIX):
            continue
        try:
            value = json.loads(line[len(PROVENANCE_PREFIX) :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            latest = value
    return latest


def strip_effort(model: str) -> str:
    base, separator, suffix = model.rpartition(":")
    return base if separator and suffix in EFFORT_SUFFIXES else model


def reliable_tokens(meta: dict[str, object]) -> int:
    usage = meta.get("usage")
    usage = usage if isinstance(usage, dict) else meta
    total = usage.get("total_tokens", usage.get("totalTokens", usage.get("total")))
    if isinstance(total, (int, float)) and total > 0:
        return int(total)
    values = [
        usage.get("input_tokens", usage.get("inputTokens", usage.get("input"))),
        usage.get("output_tokens", usage.get("outputTokens", usage.get("output"))),
    ]
    if all(isinstance(value, (int, float)) and value >= 0 for value in values):
        return int(sum(values))
    return 0


def positive_cost(meta: dict[str, object]) -> float | None:
    cost = meta.get("cost")
    return float(cost) if isinstance(cost, (int, float)) and cost > 0 else None


def validate_chunk(text: str, start: int, end: int) -> None:
    if not text.strip().endswith(f"<!-- PPT2MD_CHUNK_END:{start}-{end} -->"):
        raise ValueError(f"chunk {start}-{end} is missing its final delimiter")
    chunk_delimiter = f"<!-- PPT2MD_CHUNK_END:{start}-{end} -->"
    chunk_delimiters = re.findall(r"<!-- PPT2MD_CHUNK_END:(\d+-\d+) -->", text)
    if chunk_delimiters != [f"{start}-{end}"] or text.count(chunk_delimiter) != 1:
        raise ValueError(f"chunk {start}-{end} has an incorrect delimiter count")
    headings = [int(match.group(1)) for match in HEADER_RE.finditer(text)]
    if headings != list(range(start, end + 1)):
        raise ValueError(f"chunk {start}-{end} has unexpected slide headings")
    slide_delimiters = [
        int(number)
        for number in re.findall(r"<!-- PPT2MD_SLIDE_END:(\d+) -->", text)
    ]
    if slide_delimiters != list(range(start, end + 1)):
        raise ValueError(f"chunk {start}-{end} has unexpected slide delimiters")
    for number in range(start, end + 1):
        delimiter = f"<!-- PPT2MD_SLIDE_END:{number} -->"
        header_match = list(
            re.finditer(rf"^## 슬라이드 {number}$", text, flags=re.MULTILINE)
        )
        if len(header_match) != 1 or text.count(delimiter) != 1:
            raise ValueError(f"slide {number} header or delimiter is not exact")
        header_position = header_match[0].end()
        delimiter_position = text.index(delimiter)
        if delimiter_position <= header_position or not text[header_position:delimiter_position].strip():
            raise ValueError(f"slide {number} has no complete body")
    for number in range(start, end):
        # ponytail: slide-end N must precede header N+1 — otherwise clustered
        # end markers could pass with misattributed or empty bodies.
        next_header = re.search(
            rf"^## 슬라이드 {number + 1}$", text, flags=re.MULTILINE
        )
        end_position = text.index(f"<!-- PPT2MD_SLIDE_END:{number} -->")
        if next_header is None or end_position > next_header.start():
            raise ValueError(
                f"slide {number} end delimiter does not precede slide {number + 1} header"
            )
    if text.index(chunk_delimiter) < text.index(
        f"<!-- PPT2MD_SLIDE_END:{end} -->"
    ):
        raise ValueError(f"chunk {start}-{end} delimiter precedes final slide")


def atomic_publish(dest: Path, content: str) -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{dest.stem}.md-", suffix=".tmp", dir=dest.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, dest)
        directory_fd = os.open(dest.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def preflight(slide_count: int, chunk_count: int, seat: str) -> None:
    print(
        "ppt2md preflight: "
        f"slides={slide_count} chunks={chunk_count} seat={seat} "
        f"caps=slides:{MAX_SLIDES},chunks:{MAX_CHUNKS},"
        f"chunk_seconds:{int(CHUNK_TIMEOUT)},total_seconds:{int(TOTAL_TIMEOUT)},"
        f"tokens:{MAX_TOKENS}",
        flush=True,
    )


def convert(pdf: Path, *, runner: Runner | None = None) -> int:
    if runner is None:
        runner = run_helper
    pdf_path = resolve_pdf(pdf)
    dest = destination(pdf_path)
    # ponytail: quarantine the prior canonical immediately after resolving the
    # completed PDF, before discovery/seat/cap validation — a fresh capture must
    # never sit beside a stale canonical when any later step fails. On failure
    # the quarantine is retained (canonical absent, per the approved contract).
    quarantine = quarantine_prior(dest)
    slides = discover_slides(pdf_path)
    slide_count = len(slides)
    chunk_count = math.ceil(slide_count / CHUNK_SIZE)
    model_override = os.environ.get("PPT2MD_MODEL", "").strip()
    seat = model_override or DEFAULT_MODEL
    if "/" not in seat:
        raise ValueError("PPT2MD_MODEL must be provider/model")
    provider, expected_model = seat.split("/", 1)
    if slide_count > MAX_SLIDES or chunk_count > MAX_CHUNKS:
        preflight(slide_count, chunk_count, seat)
        raise ValueError("slide or chunk cap exceeded")
    preflight(slide_count, chunk_count, seat)
    deadline = time.monotonic() + TOTAL_TIMEOUT
    total_tokens = 0
    costs: list[float | None] = []
    chunks: list[str] = []
    try:
        for start in range(1, slide_count + 1, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE - 1, slide_count)
            remaining = deadline - time.monotonic()
            if remaining <= 0 or total_tokens >= MAX_TOKENS:
                raise ValueError("total time or reliable token cap reached before next chunk")
            prompt = prompt_for(slides, start, end)
            attachment_args = [f"@{slide}" for slide in slides[start - 1 : end]]
            selector_args = ["--model", seat]
            command = [
                sys.executable,
                str(HELPER),
                "--timeout",
                str(min(CHUNK_TIMEOUT, remaining)),
                "--expect-provider",
                provider,
                "--expect-model",
                expected_model,
                "--",
                os.environ.get("GJC_BIN", "gjc"),
                "-p",
                "--no-session",
                "--mode",
                "json",
                "--no-tools",
                *selector_args,
                *attachment_args,
                prompt,
            ]
            result = runner(command, min(CHUNK_TIMEOUT, remaining))
            if result.returncode != 0:
                raise ValueError(f"model chunk {start}-{end} failed (rc={result.returncode})")
            if time.monotonic() > deadline:
                raise ValueError("total time cap reached after model chunk")
            validate_chunk(result.stdout, start, end)
            meta = parse_helper_meta(result.stderr)
            if not meta:
                raise ValueError("model chunk is missing provenance metadata")
            actual_provider = meta.get("provider")
            actual_model = meta.get("model")
            if (
                actual_provider != provider
                or not isinstance(actual_model, str)
                or strip_effort(actual_model) != strip_effort(expected_model)
            ):
                raise ValueError("model chunk provenance metadata mismatch")
            total_tokens += reliable_tokens(meta)
            if total_tokens > MAX_TOKENS:
                raise ValueError("reliable token cap exceeded")
            costs.append(positive_cost(meta))
            chunks.append(result.stdout.strip())
        content = "\n\n".join(chunks) + "\n"
        atomic_publish(destination(pdf_path), content)
        if quarantine is not None:
            quarantine.unlink()
        cost: object = sum(costs) if costs and all(value is not None for value in costs) else "unknown"
        print(
            META_PREFIX
            + json.dumps(
                {
                    "schema_version": 1,
                    "provider": provider,
                    "model": expected_model,
                    "usage": {"reliable_tokens": total_tokens},
                    "cost": cost,
                },
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 0
    except Exception:
        # ponytail: generation-owned cleanup — the canonical is already absent
        # because WE quarantined it; never unlink the shared destination on
        # failure, or a concurrent writer's successful output could be deleted.
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    try:
        return convert(args.pdf)
    except (OSError, ValueError) as error:
        print(f"ppt2md: {error}", file=sys.stderr)
        return MD_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
