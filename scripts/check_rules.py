#!/usr/bin/env python3
"""Check Antigravity rule frontmatter for rules/*.md.

Antigravity silently discards a rules/*.md file whose YAML frontmatter is
missing or has an invalid `trigger` (https://antigravity.google/docs/rules/).

This is NOT a full YAML parser. It validates the flat `key: value` subset that
Antigravity rule frontmatter uses (plain, single-quoted, double-quoted scalars).
Anything outside that subset is reported as an error.
"""
import sys
from pathlib import Path

TRIGGERS = {"always_on", "model_decision", "glob", "manual"}
MAX_BYTES = 24000


def unquote(raw):
    """Return (value, error). Handles plain, 'single' and "double" scalars."""
    raw = raw.strip()
    if not raw:
        return "", None
    if raw[0] in "\"'":
        quote = raw[0]
        if len(raw) < 2 or raw[-1] != quote:
            return None, "unbalanced quote"
        inner = raw[1:-1]
        if quote == "'":
            inner = inner.replace("''", "'")
        elif '"' in inner.replace('\\"', ""):
            return None, "unescaped quote inside double-quoted value"
        return inner.replace('\\"', '"') if quote == '"' else inner, None
    if raw[0] == "*":
        return None, "unquoted value starts with '*' (YAML alias); wrap in quotes"
    return raw.split(" #")[0].strip(), None


def check(path):
    errors = []
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        errors.append(f"over {MAX_BYTES} bytes ({len(data)})")
    lines = data.decode("utf-8").splitlines()
    if not lines or lines[0].rstrip() != "---":
        return errors + ["missing opening '---' on line 1"]
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None:
        return errors + ["missing closing '---'"]
    fields = {}
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line or line[0] in " \t":
            errors.append(f"line {number}: expected flat 'key: value'")
            continue
        key, _, raw = line.partition(":")
        value, problem = unquote(raw)
        if problem:
            errors.append(f"line {number}: {key.strip()}: {problem}")
            continue
        fields[key.strip()] = value
    trigger = fields.get("trigger")
    if trigger is None:
        errors.append("missing trigger")
    elif trigger not in TRIGGERS:
        errors.append(f"invalid trigger '{trigger}'")
    if trigger == "model_decision" and not fields.get("description"):
        errors.append("model_decision requires a non-empty description")
    if "description" in fields and not fields["description"]:
        errors.append("description is empty")
    if trigger == "glob" and not (fields.get("globs") or fields.get("glob")):
        errors.append("glob trigger requires non-empty globs")
    return errors


def main(argv):
    targets = [Path(a) for a in argv] or sorted(
        (Path(__file__).resolve().parent.parent / "rules").glob("*.md")
    )
    failed = False
    for target in targets:
        for error in check(target):
            print(f"FAIL {target}: {error}")
            failed = True
    if not failed:
        print(f"OK: {len(targets)} rule file(s) pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
