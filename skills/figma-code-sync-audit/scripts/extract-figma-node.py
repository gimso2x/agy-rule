#!/usr/bin/env python3
"""Extract Figma node trees as lossless JSON or the legacy text summary.

JSON output deliberately contains no design-system or implementation policy.  The
``document`` field is the Figma response document verbatim; ``index`` is only a
searchable projection with convenience values under ``normalized``.

Usage:
  FIGMA_TOKEN=... python3 extract-figma-node.py [--format text] <file_key> <node_id>
  FIGMA_TOKEN=... python3 extract-figma-node.py --format json <file_key> <node_id>
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


KNOWN_NODE_TYPES = {
    "TEXT",
    "FRAME",
    "INSTANCE",
    "COMPONENT",
    "COMPONENT_SET",
    "GROUP",
    "VECTOR",
    "BOOLEAN_OPERATION",
    "ELLIPSE",
    "RECTANGLE",
    "LINE",
}


def normalize_node_id(raw: str) -> str:
    return raw.strip().replace("-", ":")


def rgba(color: dict[str, Any] | None) -> str:
    if not color:
        return ""
    r = round(float(color.get("r", 0)) * 255)
    g = round(float(color.get("g", 0)) * 255)
    b = round(float(color.get("b", 0)) * 255)
    a = color.get("a")
    if a is None or float(a) >= 1:
        return f"rgba({r},{g},{b})"
    return f"rgba({r},{g},{b},{float(a):.3g})"


def fill_color(node: dict[str, Any]) -> str:
    """Return first visible SOLID fill, or backgroundColor fallback."""
    fills = node.get("fills") or []
    for fill in fills:
        if fill.get("visible", True) and fill.get("type") == "SOLID":
            return rgba(fill.get("color"))
    background = node.get("backgroundColor")
    return rgba(background) if background else ""


def parse_effects(node: dict[str, Any]) -> str:
    """Return formatted effect descriptions while preserving raw effects in JSON."""
    parts: list[str] = []
    for effect in node.get("effects") or []:
        if not effect.get("visible", True):
            continue
        effect_type = effect.get("type", "")
        radius = effect.get("radius")
        offset = effect.get("offset") or {}
        color = rgba(effect.get("color"))
        spread = effect.get("spread")
        if effect_type in ("DROP_SHADOW", "INNER_SHADOW"):
            label = "shadow=drop" if effect_type == "DROP_SHADOW" else "shadow=inner"
            desc = f"{label} offset={offset} blur={radius}"
            if spread:
                desc += f" spread={spread}"
            if color:
                desc += f" color={color}"
            parts.append(desc)
        elif effect_type == "LAYER_BLUR":
            parts.append(f"blur=layer radius={radius}")
        elif effect_type == "BACKGROUND_BLUR":
            parts.append(f"blur=background radius={radius}")
        else:
            parts.append(f"effect={effect_type} radius={radius} color={color}")
    return " ".join(parts)


def layout_info(node: dict[str, Any]) -> str:
    """Collect comprehensive layout / sizing / constraint information."""
    parts: list[str] = []
    bbox = node.get("absoluteBoundingBox") or {}
    if bbox:
        parts.append(f"{bbox.get('width', 0):.0f}x{bbox.get('height', 0):.0f}")
    sizing_h = node.get("layoutSizingHorizontal")
    sizing_v = node.get("layoutSizingVertical")
    if sizing_h:
        parts.append(f"sizingH={sizing_h}")
    if sizing_v:
        parts.append(f"sizingV={sizing_v}")
    if node.get("layoutMode"):
        parts.append(f"layout={node['layoutMode']}")
    if node.get("itemSpacing") is not None:
        parts.append(f"gap={node['itemSpacing']}")
    for key in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft"):
        if node.get(key) is not None:
            parts.append(f"{key}={node[key]}")
    if node.get("primaryAxisAlignItems"):
        parts.append(f"primaryAxis={node['primaryAxisAlignItems']}")
    if node.get("counterAxisAlignItems"):
        parts.append(f"counterAxis={node['counterAxisAlignItems']}")
    if node.get("counterAxisSizingMode"):
        parts.append(f"counterAxisSizing={node['counterAxisSizingMode']}")
    constraints = node.get("constraints")
    if constraints:
        h = constraints.get("horizontal", "")
        v = constraints.get("vertical", "")
        if h or v:
            parts.append(f"constraints={h}/{v}")
    opacity = node.get("opacity")
    if opacity is not None and opacity < 1.0:
        parts.append(f"opacity={opacity:.2f}")
    if node.get("clipsContent"):
        parts.append("clipsContent")
    blend = node.get("blendMode")
    if blend and blend != "PASS_THROUGH":
        parts.append(f"blend={blend}")
    if node.get("cornerRadius") is not None:
        parts.append(f"radius={node['cornerRadius']}")
    if node.get("rectangleCornerRadii"):
        parts.append(f"radii={node['rectangleCornerRadii']}")
    effects_str = parse_effects(node)
    if effects_str:
        parts.append(effects_str)
    strokes = node.get("strokes") or []
    has_visible_stroke = False
    for stroke in strokes:
        if stroke.get("visible", True):
            has_visible_stroke = True
            parts.append(f"stroke={rgba(stroke.get('color'))} weight={node.get('strokeWeight')}")
    if has_visible_stroke and node.get("strokeAlign"):
        parts.append(f"strokeAlign={node['strokeAlign']}")
    return " ".join(parts)


def component_props_info(node: dict[str, Any]) -> str:
    """Return component properties set (variant choices) as a compact string."""
    props = node.get("componentProperties")
    if not props:
        return ""
    entries: list[str] = []
    for key, val in props.items():
        name = val.get("value", "")
        if name:
            short_key = key.lstrip("#").split(":")[0] if ":" in key else key
            entries.append(f"{short_key}={name}")
    return " props={" + ", ".join(entries) + "}" if entries else ""


def bound_variables_info(node: dict[str, Any]) -> str:
    """Return bound variables summary if present."""
    bound = node.get("boundVariables")
    if not bound:
        return ""
    entries: list[str] = []
    for key, val in bound.items():
        if isinstance(val, list):
            vals = [v.get("id", "") for v in val if isinstance(v, dict)]
            if vals:
                entries.append(f"{key}=[{','.join(vals)}]")
        elif isinstance(val, dict) and val.get("id"):
            entries.append(f"{key}={val['id']}")
    return f" vars=[{', '.join(entries)}]" if entries else ""


visible_texts: list[str] = []


def walk(node: dict[str, Any], path: str = "", ancestor_hidden: bool = False) -> None:
    """Recursively walk the Figma node tree and print the legacy text format."""
    current = f"{path}/{node.get('name', '<unnamed>')}"
    node_type = node.get("type", "")
    hidden = node.get("visible", True) is False
    effective_hidden = ancestor_hidden or hidden
    marker = " [HIDDEN]" if hidden else (" [hidden-ancestor]" if effective_hidden else "")
    if node_type == "TEXT":
        style = node.get("style") or {}
        ls = node.get("letterSpacing") or {}
        ls_str = f" letterSpacing={ls}" if ls else ""
        print(
            "TEXT | "
            f"{node.get('characters', '')} | "
            f"{style.get('fontFamily', '')} {style.get('fontSize', '')}px "
            f"w{style.get('fontWeight', '')} lineHeight={style.get('lineHeightPx', '')}"
            f"{ls_str} | "
            f"{fill_color(node)} | {layout_info(node)}"
            f"{bound_variables_info(node)} | {current}{marker}"
        )
        if not effective_hidden:
            characters = str(node.get("characters", "")).strip()
            if characters:
                visible_texts.append(characters)
    elif node_type in {"FRAME", "INSTANCE", "COMPONENT", "COMPONENT_SET", "GROUP"}:
        main = f"{node_type}"
        if node.get("componentId"):
            main += f" componentId={node['componentId']}"
        main += f" | {current}{marker}"
        bg = fill_color(node)
        if bg:
            main += f" | bg={bg}"
        info = layout_info(node)
        if info:
            main += f" | {info}"
        cprops = component_props_info(node)
        if cprops:
            main += cprops
        bv = bound_variables_info(node)
        if bv:
            main += bv
        print(main)
        if hidden:
            return
    elif node_type in {"VECTOR", "BOOLEAN_OPERATION", "ELLIPSE", "RECTANGLE", "LINE"}:
        print(
            f"{node_type} | {current}{marker}"
            f" | fill={fill_color(node)}"
            f" | {layout_info(node)}"
            f"{bound_variables_info(node)}"
        )
    for child in node.get("children") or []:
        walk(child, current, effective_hidden)


def _normalized(node: dict[str, Any], effective_hidden: bool) -> dict[str, Any]:
    """Small convenience projection; raw values remain on the index node."""
    bbox = node.get("absoluteBoundingBox")
    result: dict[str, Any] = {"effectiveVisible": not effective_hidden}
    if isinstance(bbox, dict):
        result["bbox"] = {k: bbox[k] for k in ("x", "y", "width", "height") if k in bbox}
    if "layoutMode" in node:
        result["layoutMode"] = node["layoutMode"]
    if "itemSpacing" in node:
        result["gap"] = node["itemSpacing"]
    padding = {key: node[key] for key in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft") if key in node}
    if padding:
        result["padding"] = padding
    if "opacity" in node:
        result["opacity"] = node["opacity"]
    return result


def build_index(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a derived, lossless-per-property index without mutating ``document``."""
    nodes: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], path: str = "", ancestor_hidden: bool = False) -> None:
        name = node.get("name", "<unnamed>")
        current = f"{path}/{name}"
        hidden = node.get("visible", True) is False
        effective_hidden = ancestor_hidden or hidden
        indexed = copy.deepcopy(node)
        indexed.pop("children", None)
        indexed["path"] = current
        indexed["visibility"] = not effective_hidden
        indexed["normalized"] = _normalized(node, effective_hidden)
        nodes.append(indexed)
        for child in node.get("children") or []:
            if isinstance(child, dict):
                visit(child, current, effective_hidden)

    visit(document)
    return nodes


def extract_json(payload: dict[str, Any], file_key: str, node_id: str) -> dict[str, Any]:
    """Return JSON v1 representation from a Figma node response."""
    canonical_id = normalize_node_id(node_id)
    response_nodes = payload.get("nodes") or {}
    entry = response_nodes.get(canonical_id)
    if entry is None and node_id in response_nodes:
        entry = response_nodes[node_id]
    if not isinstance(entry, dict) or not isinstance(entry.get("document"), dict):
        raise KeyError(f"Figma response does not contain document for node {canonical_id}")
    document = copy.deepcopy(entry["document"])
    # Figma GetFileNodesResponse: components/componentSets/styles/schemaVersion는
    # nodes[id] entry 내부에 있다 (payload top-level에는 없다). entry 우선, fallback payload.
    metadata: dict[str, Any] = {}
    for key in ("components", "componentSets", "styles"):
        src = entry.get(key)
        if not isinstance(src, dict):
            src = payload.get(key)
        if isinstance(src, dict):
            metadata[key] = copy.deepcopy(src)
    if "schemaVersion" in entry:
        metadata["schemaVersion"] = entry["schemaVersion"]
    return {
        "schemaVersion": 1,
        "source": {"fileKey": file_key, "nodeId": canonical_id},
        "document": document,
        "metadata": metadata,
        "index": {"nodes": build_index(document)},
    }


def fetch_payload(file_key: str, node_id: str) -> dict[str, Any]:
    token = os.environ.get("FIGMA_ACCESS_TOKEN") or os.environ.get("FIGMA_TOKEN")
    if not token:
        token_file = Path.home() / ".figma_token"
        if token_file.exists():
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except OSError:
                pass
    if not token:
        raise ValueError("FIGMA_TOKEN or FIGMA_ACCESS_TOKEN is required.")
    canonical_id = normalize_node_id(node_id)
    encoded_node_id = urllib.parse.quote(canonical_id, safe="")
    url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={encoded_node_id}"
    request = urllib.request.Request(url, headers={"X-Figma-Token": token})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def parse_figma_url(url_str: str) -> tuple[str, str] | None:
    """Extract file_key and normalized node_id from a Figma URL."""
    # Pattern matches /design/:key or /file/:key, and ?node-id=... or &node-id=...
    m_key = re.search(r"figma\.com/(?:design|file)/([a-zA-Z0-9]+)", url_str)
    m_node = re.search(r"node-id=([0-9]+(?:[:-][0-9]+)?)", url_str)
    if m_key and m_node:
        return m_key.group(1), normalize_node_id(m_node.group(1))
    return None


def usage() -> str:
    return "Usage: extract-figma-node.py [--format text|json] <file_key> <node_id>\n       extract-figma-node.py [--format text|json] <figma_url>"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    output_format = "text"
    if "--format" in args:
        pos = args.index("--format")
        if pos + 1 >= len(args) or args[pos + 1] not in {"text", "json"}:
            print("--format must be text or json", file=sys.stderr)
            return 2
        output_format = args[pos + 1]
        del args[pos : pos + 2]

    if len(args) == 1 and ("figma.com" in args[0] or "http" in args[0]):
        parsed = parse_figma_url(args[0])
        if not parsed:
            print("Error: Could not parse file_key and node-id from URL.", file=sys.stderr)
            return 2
        file_key, node_id = parsed
    elif len(args) == 2:
        file_key, node_id = args[0].strip(), normalize_node_id(args[1])
    else:
        print(usage(), file=sys.stderr)
        return 2
    try:
        payload = fetch_payload(file_key, node_id)
        if output_format == "json":
            print(json.dumps(extract_json(payload, file_key, node_id), ensure_ascii=False, indent=2))
            return 0
        global visible_texts
        visible_texts = []
        document = payload["nodes"][node_id]["document"]
        walk(document)
        print(f"\n=== VISIBLE TEXT ONLY ({len(visible_texts)} items) ===")
        for text in visible_texts:
            print(f"  {text}")
        return 0
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
    except (KeyError, ValueError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
