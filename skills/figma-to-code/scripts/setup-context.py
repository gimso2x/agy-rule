#!/usr/bin/env python3
"""Global SETUP-phase context scanner — design-system agnostic.

DESIGN.md is an OPTIONAL token source. Without it (or with --no-design-md),
the scanner emits raw Figma-evidence mode: empty tokens, resolution
``unavailable``, and ``rawLiteralPermission="not-inferred"``. With a parseable
DESIGN.md, a bounded H2 grammar builds an exact token reverse map.

Three capability axes stay separated:
  1. extraction   — always lossless (handled by extract-figma-node.py)
  2. resolution   — per-category exact token capability (this scanner)
  3. policy       — host DS API + rules decide generated code (never inferred)

ponytail: bounded H2 regex parser. DESIGN.md is auto-generated so the format is
stable, but if the generator changes the parser degrades to partial/unusable
(fail-closed). A YAML-only file becomes ``unusable``. No general Markdown/YAML
parser is implemented (YAGNI); only the H2 section contract below is supported.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# --- DESIGN.md bounded grammar ------------------------------------------------

# Skip a leading ```--- ... ---``` YAML frontmatter without interpreting it.
YAML_FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
ROOT_FS_RE = re.compile(r"root[ -]?font[ -]?size[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*px", re.IGNORECASE)

# Supported H2 titles (case-insensitive substring match) → category key.
H2_CATEGORY = [
    (("color", "palette"), "colors"),
    (("typography", "type"), "typography"),
    (("spacing", "layout"), "spacing"),
    (("radius", "shape"), "radius"),
    (("shadow", "elevation"), "shadows"),
]
# Elevation aliases to both radius and shadow; handled specially below.

SOURCE_STATUS = ("parsed", "partial", "absent", "disabled", "unusable")


def _split_h2_sections(text: str) -> list[tuple[str, str]]:
    """Return [(title, body)] splitting on H2 boundaries. Body excludes the H2 line."""
    matches = list(H2_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((m.group(1).strip(), text[start:end]))
    return sections


def _normalize_hex(h: str) -> str:
    h = h.strip().lstrip("#").lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) == 4:
        h = "".join(c * 2 for c in h)
    return h  # 6 or 8 hex chars


def hex_to_rgba8(h: str) -> tuple[int, int, int, int]:
    h = _normalize_hex(h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return (r, g, b, a)


def figma_a_to_byte(a: float | None) -> int | None:
    if a is None:
        return 255
    if not isinstance(a, (int, float)) or a != a:  # NaN check
        return None
    return max(0, min(255, round(max(0.0, min(1.0, float(a))) * 255)))


# --- category parsers ---------------------------------------------------------

_COLOR_PROSE_RE = re.compile(r"-\s*\*\*(\w+)\*\*:\s*(.+)")
_COLOR_PAIR_RE = re.compile(r"(\d+)\s+#([0-9a-fA-F]{3,8})")
_COLOR_TABLE_RE = re.compile(
    r"\|\s*([\w-]+)\s+\|\s*var\(--[\w-]+\)\s+\|\s*#([0-9a-fA-F]{6,8})\s*\|"
)
_TYPO_RE = re.compile(
    r"`([\w-]+)`:\s*\w+,\s*([0-9.]+)rem,\s*([0-9]+)"
)
_SCALE_PAIR_RE = re.compile(r"(\d+)(?:\([\w-]+\))?=([0-9.]+)rem")


def parse_colors(body: str) -> tuple[list[dict], dict, list[str]]:
    """Return (tokens[{name,hex,rgba8}], reverseMap{rgba8key:[names]}, unparsed)."""
    tokens: list[dict] = []
    rev: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    unparsed: list[str] = []

    # prose: `- **gray**: 0 #ffffff, 25 #fafafb, ...`
    for m in _COLOR_PROSE_RE.finditer(body):
        family = m.group(1)
        for cm in _COLOR_PAIR_RE.finditer(m.group(2)):
            idx, hexv = cm.group(1), cm.group(2)
            name = f"{family}-{idx}"
            nh = _normalize_hex(hexv)
            if name in seen and seen[name] != nh:
                unparsed.append(f"duplicate {name}: {seen[name]} vs {nh}")
                continue
            seen[name] = nh
            r, g, b, a = hex_to_rgba8(nh)
            tokens.append({"name": name, "hex": nh, "rgba8": [r, g, b, a]})
            rev.setdefault(f"{r},{g},{b},{a}", []).append(name)

    # table: `| blue-50 | var(--color-blue-50) | #e8f1ff |`
    for m in _COLOR_TABLE_RE.finditer(body):
        name, hexv = m.group(1), m.group(2)
        nh = _normalize_hex(hexv)
        if name in seen:
            continue  # prose wins; table is supplementary
        seen[name] = nh
        r, g, b, a = hex_to_rgba8(nh)
        tokens.append({"name": name, "hex": nh, "rgba8": [r, g, b, a]})
        rev.setdefault(f"{r},{g},{b},{a}", []).append(name)

    return tokens, rev, unparsed


def parse_typography(body: str, root_fs: float | None) -> tuple[list[dict], list[str]]:
    tokens: list[dict] = []
    unparsed: list[str] = []
    for m in _TYPO_RE.finditer(body):
        name, rem_s, weight_s = m.group(1), m.group(2), m.group(3)
        rem = float(rem_s)
        weight = int(weight_s)
        px = round(rem * root_fs) if root_fs else None
        tokens.append({"name": name, "rem": rem, "px": px, "weight": weight})
    if not tokens and body.strip():
        unparsed.append("typography section present but no `token`: font, Xrem, weight matched")
    return tokens, unparsed


_NAMED_SCALE_RE = re.compile(r"([\w-]+)=([0-9.]+)%")


def parse_scale_pairs(body: str, root_fs: float | None = None) -> tuple[list[dict], list[str]]:
    tokens: list[dict] = []
    unparsed: list[str] = []
    for m in _SCALE_PAIR_RE.finditer(body):
        n, rem = int(m.group(1)), float(m.group(2))
        # px는 파싱된 root font-size에서만 유도. root 없으면 px=null (추측 금지).
        tokens.append({"name": str(n), "rem": rem, "px": round(rem * root_fs) if root_fs else None})
    # named percent scale (예: Radius `Circle=100%`) — rem이 아니므로 px=null.
    for m in _NAMED_SCALE_RE.finditer(body):
        name = m.group(1)
        if name.isdigit():
            continue  # rem 쌍과 중복 방지
        tokens.append({"name": name, "percent": float(m.group(2)), "px": None})
    if not tokens and body.strip():
        unparsed.append("scale section present but no N=Nrem matched")
    return tokens, unparsed


def parse_shadows(body: str) -> tuple[list[dict], list[str]]:
    tokens: list[dict] = []
    unparsed: list[str] = []
    # Split on `, ` only when followed by `name=` (keeps rgba commas intact).
    for chunk in re.split(r",\s*(?=\w+=)", body):
        chunk = chunk.strip()
        m = re.match(r"(\w+)=(.+)", chunk)
        if m:
            tokens.append({"name": m.group(1), "css": m.group(2).strip().rstrip(".")})
    if not tokens and body.strip():
        unparsed.append("shadow section present but no name=css matched")
    return tokens, unparsed


def parse_design_md(
    text: str, root_override: float | None
) -> tuple[dict, list[str]]:
    """Parse DESIGN.md text. Returns (design_block, warnings)."""
    warnings: list[str] = []
    body = YAML_FRONTMATTER_RE.sub("", text, count=1)
    sections = _split_h2_sections(body)
    if not sections:
        return (
            {"status": "unusable", "rootFontSizePx": None, "rootFontSizeSource": None},
            ["no H2 sections found; unusable (YAML-only or empty)"],
        )

    # root font-size: preamble before first H2.
    preamble = body[: sections[0][1].start()] if False else body[: body.find("##")]
    rmatch = ROOT_FS_RE.search(preamble) if preamble else None
    if rmatch:
        root_fs: float | None = float(rmatch.group(1))
        root_src = "design-md"
    elif root_override:
        root_fs = root_override
        root_src = "cli"
    else:
        root_fs = None
        root_src = None
        if root_override is None:
            warnings.append("root font-size not found and --root-font-size not given; typography px=null")

    raw_tokens: dict[str, Any] = {}
    raw_rev: dict[str, Any] = {}
    cats: dict[str, dict] = {}
    all_ok = True

    for title, sbody in sections:
        tlow = title.lower()
        if "elevation" in tlow:
            # Elevation은 Radius scale + Shadow scale 라인이 한 섹션에 공존.
            # 라인 단위로 분리해 각각 파싱해야 혼입(radius → shadow 오인)이 없다.
            radius_lines = "\n".join(l for l in sbody.splitlines() if re.search(r"radius", l, re.I))
            shadow_lines = "\n".join(
                re.sub(r"^[^:\n]+:\s*", "", l)
                for l in sbody.splitlines()
                if re.search(r"shadow", l, re.I)
            )
            r_tok, _ = parse_scale_pairs(radius_lines, root_fs)
            s_tok, _ = parse_shadows(shadow_lines)
            raw_tokens["radius"] = r_tok
            raw_tokens["shadows"] = s_tok
            cats["radius"] = {"status": "parsed" if r_tok else "absent", "parsedCount": len(r_tok), "unparsedExamples": []}
            cats["shadows"] = {"status": "parsed" if s_tok else "absent", "parsedCount": len(s_tok), "unparsedExamples": []}
            if not r_tok and not s_tok:
                all_ok = False
            continue
        cat = None
        for keys, c in H2_CATEGORY:
            if c in ("radius", "shadows"):
                continue
            if any(k in tlow for k in keys):
                cat = c
                break
        if cat is None:
            for keys, c in H2_CATEGORY:
                if any(k in tlow for k in keys):
                    cat = c
                    break
        if cat is None:
            continue
        if cat == "colors":
            toks, rev, un = parse_colors(sbody)
            raw_tokens["colors"] = toks
            raw_rev["colorsByRgba8"] = rev
        elif cat == "typography":
            toks, un = parse_typography(sbody, root_fs)
            raw_tokens["typography"] = toks
        elif cat == "spacing":
            toks, un = parse_scale_pairs(sbody, root_fs)
            raw_tokens["spacing"] = toks
        elif cat == "radius":
            toks, un = parse_scale_pairs(sbody, root_fs)
            raw_tokens["radius"] = toks
        elif cat == "shadows":
            toks, un = parse_shadows(sbody)
            raw_tokens["shadows"] = toks
        cats[cat] = {
            "status": "parsed" if toks else "absent",
            "parsedCount": len(toks),
            "unparsedExamples": [{"text": u[:120]} for u in un[:5]],
        }
        if un:
            warnings.extend(un[:3])
            all_ok = False

    # Ensure all 5 categories present with consistent key set.
    for c in ("colors", "typography", "spacing", "radius", "shadows"):
        raw_tokens.setdefault(c, [])
        cats.setdefault(c, {"status": "absent", "parsedCount": 0, "unparsedExamples": []})
    raw_rev.setdefault("colorsByRgba8", {})

    has_any = any(raw_tokens.get(c) for c in ("colors", "typography", "spacing", "radius", "shadows"))
    status = "parsed" if (has_any and all_ok) else ("partial" if has_any else "unusable")

    design = {
        "mode": "token-aware" if has_any else "raw",
        "source": {
            "status": status,
            "rootFontSizePx": root_fs,
            "rootFontSizeSource": root_src,
        },
        "tokens": raw_tokens,
        "reverseMaps": raw_rev,
        "categories": cats,
        "warnings": warnings,
    }
    return design, warnings


# --- design-system discovery --------------------------------------------------

IMPORT_RE = re.compile(
    r"""(?:import|export)\s[^;]*?from\s*['"]([@/\w][\w@/.\-]*)['"]"""
    r"""|require\(\s*['"]([@/\w][\w@/.\-]*)['"]\s*\)"""
    r"""|import\(\s*['"]([@/\w][\w@/.\-]*)['"]\s*\)""",
    re.MULTILINE,
)
SRC_GLOBS = ("*.ts", "*.tsx", "*.js", "*.jsx", "*.mjs", "*.cjs")
SCOPED_OR_BARE = re.compile(r"^(@[\w.-]+/[\w.-]+|[\w][\w.-]*)$")


def scan_source_imports(project_root: Path) -> dict[str, list[str]]:
    """Return {bare_package: [specifiers observed]} from src/** static imports."""
    observed: dict[str, list[str]] = {}
    src = project_root / "src"
    if not src.is_dir():
        return observed
    for f in src.rglob("*"):
        if not f.is_file() or f.suffix not in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in IMPORT_RE.finditer(text):
            spec = next((g for g in m.groups() if g), None)
            if not spec:
                continue
            pkg = spec.split("/")[0] if not spec.startswith("@") else "/".join(spec.split("/")[:2])
            if not SCOPED_OR_BARE.match(pkg):
                continue
            observed.setdefault(pkg, [])
            if spec not in observed[pkg]:
                observed[pkg].append(spec)
    return observed


def read_package_deps(project_root: Path) -> dict[str, str]:
    pj = project_root / "package.json"
    if not pj.is_file():
        return {}
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(data.get(key, {}))
    return deps


def _node_modules_root(project_root: Path) -> Path | None:
    for cand in (project_root / "node_modules",):
        if cand.is_dir():
            return cand
    return None


def _package_dir(nm: Path, pkg: str) -> Path | None:
    d = nm / pkg
    return d if d.is_dir() else None


def _is_types_path(p: str | None) -> bool:
    """typesPath 후보: .d.ts 계열만. .css/.js/.json 기본 타깃은 type evidence가 아니다."""
    return bool(p) and p.endswith((".d.ts", ".d.mts", ".d.cts"))


def _read_dts_exports(pdir: Path, types_path: str | None, _depth: int = 0) -> list[str]:
    """Depth-bounded .d.ts re-export 해석 → exported symbol 목록.

    ponytail: `export declare const|function|class|interface|type|enum X`,
    `export {A, B} from`, `export * from "./sub"`(depth-1 재귀)만 해석한다.
    그보다 깊은 체인/동적 문법은 빈 결과로 두고 warning 대신 조용히 누락
    (declaration을 파싱 실패해도 후보 전체를 버리지 않는다는 계약 유지).
    """
    if _depth > 1 or not types_path or not _is_types_path(types_path):
        return []
    dts = pdir / types_path
    if not dts.is_file():
        return []
    try:
        text = dts.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    names: set[str] = set()
    for m in re.finditer(
        r"export\s+(?:declare\s+)?(?:const|function|class|interface|type|enum)\s+(\w+)", text
    ):
        names.add(m.group(1))
    for m in re.finditer(r"export\s*\{([^}]*)\}\s*from\s*['\"]([^'\"]+)['\"]", text):
        for part in m.group(1).split(","):
            part = part.strip()
            if not part or part == "*":
                continue
            # `default as Button` / `Button as Foo` → public 이름은 `as` 오른쪽
            exported = part.split(" as ")[-1].strip()
            if exported:
                names.add(exported)
    for m in re.finditer(r"export\s+\*\s+from\s*['\"]([^'\"]+)['\"]", text):
        sub_rel = m.group(1)
        if sub_rel.startswith("."):
            sub_abs = (dts.parent / sub_rel).resolve()
            if not sub_abs.is_file() and not sub_abs.suffix:
                # 확장자 없는 re-export("./entries/button") → .d.ts 보정
                cand = Path(str(sub_abs) + ".d.ts")
                if cand.is_file():
                    sub_abs = cand
            pdir_abs = pdir.resolve()
            if str(sub_abs).startswith(str(pdir_abs)):
                rel = sub_abs.relative_to(pdir_abs)
                names.update(_read_dts_exports(pdir, str(rel), _depth + 1))
    return sorted(names)


def resolve_module_types(nm: Path, pkg: str, observed_specifiers: list[str] | None = None) -> list[dict]:
    """Best-effort module types from installed package exports/types. No runtime code.

    exports(./*): types 키 우선, default가 .d.ts면 대체. .css/.js/.json default는
    typesPath에서 제외해 "모든 default target이 typesPath" 오판을 막는다.
    wildcard `./*`는 observed concrete specifier(예: @proptier/ground/button)로
    치환해 실제 .d.ts를 읽는다 — literal wildcard는 그대로 두지 않는다.
    """
    observed = observed_specifiers or []
    pdir = _package_dir(nm, pkg)
    if not pdir:
        return []
    ppj = pdir / "package.json"
    if not ppj.is_file():
        return []
    try:
        pdata = json.loads(ppj.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    exports = pdata.get("exports", {})
    modules: list[dict] = []
    types_field = pdata.get("types") or pdata.get("typings")
    if types_field and isinstance(types_field, str) and _is_types_path(types_field):
        modules.append({"specifier": pkg, "typesPath": types_field, "exports": _read_dts_exports(pdir, types_field)})
    if isinstance(exports, dict):
        for key, val in exports.items():
            if key == "./*" and isinstance(val, dict) and isinstance(val.get("types"), str) and "*" in val["types"]:
                # wildcard → observed concrete subpath 치환 (예: @proptier/ground/button)
                prefix = f"{pkg}/"
                pattern = val["types"]  # "./dist/*.d.ts"
                for spec in observed:
                    if not spec.startswith(prefix):
                        continue
                    subpath = spec[len(prefix):]
                    concrete = pattern.replace("*", subpath)
                    if _is_types_path(concrete):
                        modules.append({"specifier": spec, "typesPath": concrete, "exports": _read_dts_exports(pdir, concrete)})
                continue
            if not key.startswith("./"):
                continue
            sub = f"{pkg}{key[1:]}"  # @scope/ds/button
            tpath: str | None = None
            if isinstance(val, dict):
                tv = val.get("types")
                if isinstance(tv, str) and _is_types_path(tv):
                    tpath = tv
                else:
                    dv = val.get("default")
                    if isinstance(dv, str) and _is_types_path(dv):
                        tpath = dv
            elif isinstance(val, str) and _is_types_path(val):
                tpath = val
            if tpath:
                modules.append({"specifier": sub, "typesPath": tpath, "exports": _read_dts_exports(pdir, tpath)})
    # Deduplicate by specifier.
    seen: set[str] = set()
    out: list[dict] = []
    for mod in modules:
        if mod["specifier"] in seen:
            continue
        seen.add(mod["specifier"])
        out.append(mod)
    return out


def discover_design_systems(
    project_root: Path, cli_packages: list[str]
) -> dict:
    """Return {selection:{status}, candidates:[...]} with evidence-backed candidates."""
    candidates: dict[str, dict] = {}
    deps = read_package_deps(project_root)
    imports = scan_source_imports(project_root)
    nm = _node_modules_root(project_root)

    def add(pkg: str, source: str, confidence: str):
        c = candidates.setdefault(
            pkg,
            {
                "package": pkg,
                "sources": [],
                "confidence": confidence,
                "declaredVersion": deps.get(pkg),
                "installedVersion": None,
                "installed": False,
                "observedSpecifiers": [],
                "modules": [],
            },
        )
        if source not in c["sources"]:
            c["sources"].append(source)
        rank = {"high": 3, "medium": 2, "low": 1}
        if rank.get(confidence, 0) > rank.get(c["confidence"], 0):
            c["confidence"] = confidence

    for pkg in cli_packages:
        add(pkg, "cli", "high")
    for pkg in imports:
        conf = "high" if pkg in deps else "medium"
        add(pkg, "source-import", conf)
        c = candidates[pkg]
        for spec in imports[pkg]:
            if spec not in c["observedSpecifiers"]:
                c["observedSpecifiers"].append(spec)
    for pkg in deps:
        # package marker: dependency with a design.md or design-system hint
        if nm and _package_dir(nm, pkg):
            if (nm / pkg / "design.md").is_file():
                add(pkg, "package-marker", "medium")

    if nm:
        for pkg, c in candidates.items():
            pdir = _package_dir(nm, pkg)
            if pdir:
                c["installed"] = True
                ppj = pdir / "package.json"
                if ppj.is_file():
                    try:
                        c["installedVersion"] = json.loads(ppj.read_text(encoding="utf-8")).get("version")
                    except (OSError, json.JSONDecodeError):
                        pass
                c["modules"] = resolve_module_types(nm, pkg, c.get("observedSpecifiers") or [])

    cand_list = sorted(candidates.values(), key=lambda x: x["package"])
    # ponytail: "ui"/"components" are too broad (matches floating-ui, radix-ui);
    # restrict to explicit DS hints. design.md presence is strong evidence alone.
    DS_HINT = re.compile(r"(design|ds|ground|theme|tokens)", re.IGNORECASE)
    cli_set = set(cli_packages)
    filtered = [
        c for c in cand_list
        if c["package"] in cli_set
        or DS_HINT.search(c["package"])
        or (c["installed"] and nm and (nm / c["package"] / "design.md").is_file())
    ]
    status = "single" if len(filtered) == 1 else ("multiple" if len(filtered) > 1 else "none")
    return {"selection": {"status": status}, "candidates": filtered}


# --- project context (agnostic) ----------------------------------------------

def scan_features(project_root: Path, feature_filter: str | None) -> dict:
    result: dict = {"features": [], "screens": [], "domains": []}
    features_dir = project_root / "src" / "features"
    if not features_dir.is_dir():
        return result
    for d in sorted(features_dir.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        if feature_filter and name != feature_filter:
            continue
        result["features"].append(name)
        comps = d / "components"
        if comps.is_dir():
            for c in sorted(comps.iterdir()):
                if c.is_dir():
                    result["domains"].append(f"{name}/{c.name}")
    return result


def scan_active_routes(project_root: Path) -> list:
    routes: list = []
    app_dir = project_root / "src" / "app"
    if not app_dir.is_dir():
        return routes
    for p in sorted(app_dir.rglob("page.tsx")):
        routes.append(str(p.relative_to(project_root)))
    return routes


# --- main ---------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Global figma-skill SETUP context scanner")
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--design-md", default=None, help="explicit DESIGN.md path")
    ap.add_argument("--no-design-md", action="store_true", help="disable token resolution")
    ap.add_argument("--design-system-package", action="append", default=[], dest="ds_packages")
    ap.add_argument("--root-font-size", type=float, default=None)
    ap.add_argument("--design-profile", default=None)
    ap.add_argument("--feature", default=None)
    args = ap.parse_args()

    if args.no_design_md and args.design_md:
        print("--no-design-md and --design-md are mutually exclusive", file=sys.stderr)
        return 2
    if args.root_font_size is not None and args.root_font_size <= 0:
        print("--root-font-size must be a positive number", file=sys.stderr)
        return 2

    project_root = Path(args.project_root).resolve() if args.project_root else Path.cwd()
    if not (project_root / "package.json").is_file():
        # walk up
        cur = project_root
        for _ in range(6):
            if (cur / "package.json").is_file():
                project_root = cur
                break
            cur = cur.parent

    # --- design ---
    warnings: list[str] = []
    if args.no_design_md:
        design = _raw_design_block(disabled=True)
        design["source"]["status"] = "disabled"
    else:
        dpath = Path(args.design_md) if args.design_md else (project_root / "DESIGN.md")
        if dpath.is_file():
            try:
                text = dpath.read_text(encoding="utf-8")
            except OSError as e:
                print(f"cannot read {dpath}: {e}", file=sys.stderr)
                return 2
            design, dwarn = parse_design_md(text, args.root_font_size)
            design["source"]["path"] = str(dpath)
            if args.design_profile:
                design["source"]["profile"] = args.design_profile
            warnings.extend(dwarn)
        else:
            if args.design_md:
                print(f"explicit --design-md not found: {dpath}", file=sys.stderr)
                return 2
            design = _raw_design_block()

    # --- design systems ---
    dsys = discover_design_systems(project_root, args.ds_packages)

    # --- project context ---
    feat = scan_features(project_root, args.feature)
    routes = scan_active_routes(project_root)

    pj = project_root / "package.json"
    pm = None
    if pj.is_file():
        try:
            pm = json.loads(pj.read_text(encoding="utf-8")).get("packageManager")
        except (OSError, json.JSONDecodeError):
            pass

    rule_files = [f for f in ("AGENTS.md", "CLAUDE.md") if (project_root / f).is_file()]

    output = {
        "schemaVersion": 1,
        "project": {
            "root": str(project_root),
            "manifest": "package.json" if pj.is_file() else None,
            "packageManager": pm,
            "ruleFiles": rule_files,
        },
        "design": design,
        "designSystems": dsys,
        "implementationPolicy": {
            "authority": "host",
            "ruleFiles": rule_files,
            "rawLiteralPermission": "not-inferred",
        },
        "projectContext": {
            "features": feat.get("features", []),
            "screens": feat.get("screens", []),
            "domains": feat.get("domains", []),
            "routes": routes,
        },
        "warnings": warnings,
    }
    # resolution per category
    res: dict[str, dict] = {}
    for c in ("colors", "typography", "spacing", "radius", "shadows"):
        toks = design.get("tokens", {}).get(c, [])
        res[c] = {"status": "exact" if toks else "unavailable", "exactReverseMapAvailable": bool(toks)}
    output["design"]["resolution"] = res

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _raw_design_block(disabled: bool = False) -> dict:
    base = {
        "mode": "raw",
        "source": {"status": "absent", "rootFontSizePx": None, "rootFontSizeSource": None},
        "tokens": {c: [] for c in ("colors", "typography", "spacing", "radius", "shadows")},
        "reverseMaps": {"colorsByRgba8": {}},
        "categories": {
            c: {"status": "absent", "parsedCount": 0, "unparsedExamples": []}
            for c in ("colors", "typography", "spacing", "radius", "shadows")
        },
        "warnings": [],
    }
    if disabled:
        base["source"]["status"] = "disabled"
    return base


if __name__ == "__main__":
    raise SystemExit(main())
