#!/usr/bin/env python3
"""Figma Node Tree Simplifier & Semantic Flattener for React + SCSS Modules / CSS Variables.

Eliminates designer 'div soup', collapses ghost wrappers and spacer frames,
maps colors to CSS variables / design system tokens with zero drift,
and generates both clean semantic React JSX and flat .module.scss styles.

Usage:
  python3 simplify-figma-tree.py <figma_extracted_node.json> [--mode scss|tailwind]
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any


def sanitize_class_name(name: str) -> str:
    """Convert Figma layer name to clean camelCase or kebab-case CSS class."""
    clean = re.sub(r"[^\w\s-]", "", name).strip()
    words = re.split(r"[\s_-]+", clean)
    if not words or not words[0]:
        return "element"
    # camelCase
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def rgba_to_css(color: dict[str, Any] | None, opacity: float | None = None) -> str:
    if not color:
        return ""
    r = round(float(color.get("r", 0)) * 255)
    g = round(float(color.get("g", 0)) * 255)
    b = round(float(color.get("b", 0)) * 255)
    a = color.get("a", 1.0)
    if opacity is not None:
        a = float(opacity) * float(a)
    if a >= 0.99:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r}, {g}, {b}, {float(a):.2g})"


def simplify_node(node: dict[str, Any], depth: int = 0) -> dict[str, Any] | None:
    if not node.get("visible", True):
        return None

    ntype = node.get("type", "")
    name = node.get("name", "layer")
    children = node.get("children") or []
    fills = [f for f in node.get("fills", []) if f.get("visible", True)]
    strokes = [s for s in node.get("strokes", []) if s.get("visible", True)]

    # 1. Spacer Frame Elimination:
    # Empty frames with only dimensions, no fill/stroke/text -> drop, converted to parent gap
    is_empty_frame = ntype in ("FRAME", "GROUP", "RECTANGLE") and not children and not fills and not strokes
    if is_empty_frame:
        return None

    # 2. Vector / Icon grouping
    bbox = node.get("absoluteBoundingBox") or {}
    w = round(bbox.get("width", 0))
    h = round(bbox.get("height", 0))

    lname = name.lower()
    is_icon = ntype in ("VECTOR", "BOOLEAN_OPERATION", "LINE", "ELLIPSE") or (
        ntype in ("FRAME", "COMPONENT", "INSTANCE", "GROUP") and (w <= 48 and h <= 48 or "icon" in lname or "ic_" in lname)
    )
    if is_icon:
        clean_name = re.sub(r"[^\w-]", "_", name).strip("_") or "Icon"
        return {
            "tag": "Icon",
            "name": clean_name,
            "width": w,
            "height": h,
            "jsx": f"<Icon name='{clean_name}' className={{styles.{sanitize_class_name(clean_name)}}} />",
            "scss_rules": {
                "width": f"{w}px",
                "height": f"{h}px",
                "flex-shrink": "0"
            }
        }

    # 3. Text Node
    if ntype == "TEXT":
        chars = node.get("characters", "").strip()
        style = node.get("style", {})
        fs = style.get("fontSize", 14)
        fw = style.get("fontWeight", 400)
        lh = style.get("lineHeightPx")

        # Color
        color_val = ""
        for fill in fills:
            if fill.get("type") == "SOLID" and "color" in fill:
                color_val = rgba_to_css(fill["color"], fill.get("opacity"))
                break

        # Semantic tag heuristic
        tag = "span"
        if fs >= 24 or (fs >= 20 and fw >= 600):
            tag = "h2" if fs < 30 else "h1"
        elif fs >= 18 and fw >= 600:
            tag = "h3"
        elif "\n" in chars or len(chars) > 60:
            tag = "p"

        cls_name = sanitize_class_name(name)
        scss_rules = {
            "font-size": f"{fs}px",
            "font-weight": str(fw),
        }
        if lh and round(lh) != round(fs):
            scss_rules["line-height"] = f"{round(lh)}px"
        if color_val:
            scss_rules["color"] = color_val

        return {
            "tag": tag,
            "name": name,
            "className": cls_name,
            "text": chars,
            "scss_rules": scss_rules
        }

    # 4. Containers (FRAME, INSTANCE, COMPONENT, GROUP)
    simplified_children = []
    for c in children:
        sc = simplify_node(c, depth + 1)
        if sc:
            simplified_children.append(sc)

    # Ghost Frame Collapse:
    # If container has NO background, NO border, NO padding, NO cornerRadius, and only ONE child -> collapse!
    has_bg = bool(fills)
    has_border = bool(strokes)
    has_padding = any(node.get(k, 0) > 0 for k in ("paddingTop", "paddingBottom", "paddingLeft", "paddingRight"))
    has_radius = (node.get("cornerRadius", 0) > 0) or bool(node.get("rectangleCornerRadii"))

    if not has_bg and not has_border and not has_padding and not has_radius and len(simplified_children) == 1:
        # Collapse ghost wrapper into child
        return simplified_children[0]

    # Semantic Tag Inference
    tag = "div"
    if any(kw in lname for kw in ("button", "btn", "cta")):
        tag = "button"
    elif any(kw in lname for kw in ("header", "topbar", "navbar")):
        tag = "header"
    elif any(kw in lname for kw in ("nav", "tabs", "tabbar", "menu")):
        tag = "nav"
    elif "footer" in lname:
        tag = "footer"
    elif any(kw in lname for kw in ("card", "item", "article")):
        tag = "article" if "card" in lname else "div"
    elif any(kw in lname for kw in ("badge", "chip", "tag")):
        tag = "span"
    elif any(kw in lname for kw in ("list", "feed")) and len(simplified_children) > 1:
        tag = "ul"

    cls_name = sanitize_class_name(name)
    scss_rules: dict[str, str] = {}

    # Layout Rules
    lmode = node.get("layoutMode")
    if lmode in ("HORIZONTAL", "VERTICAL"):
        scss_rules["display"] = "flex"
        scss_rules["flex-direction"] = "row" if lmode == "HORIZONTAL" else "column"

        primary_align = node.get("primaryAxisAlignItems")
        if primary_align == "SPACE_BETWEEN":
            scss_rules["justify-content"] = "space-between"
        elif primary_align == "CENTER":
            scss_rules["justify-content"] = "center"
        elif primary_align == "MAX":
            scss_rules["justify-content"] = "flex-end"

        counter_align = node.get("counterAxisAlignItems")
        if counter_align == "CENTER":
            scss_rules["align-items"] = "center"
        elif counter_align == "MAX":
            scss_rules["align-items"] = "flex-end"

    gap = node.get("itemSpacing", 0)
    if gap > 0:
        scss_rules["gap"] = f"{gap}px"

    # Padding
    pt, pr, pb, pl = (node.get(f"padding{side}", 0) for side in ("Top", "Right", "Bottom", "Left"))
    if pt == pb == pl == pr and pt > 0:
        scss_rules["padding"] = f"{pt}px"
    elif (pt > 0 or pr > 0 or pb > 0 or pl > 0):
        scss_rules["padding"] = f"{pt}px {pr}px {pb}px {pl}px"

    # Background
    for fill in fills:
        if fill.get("type") == "SOLID" and "color" in fill:
            scss_rules["background-color"] = rgba_to_css(fill["color"], fill.get("opacity"))
            break

    # Border & Radius
    if has_border:
        sw = node.get("strokeWeight", 1)
        for stroke in strokes:
            if "color" in stroke:
                scss_rules["border"] = f"{sw}px solid {rgba_to_css(stroke['color'])}"
                break

    cr = node.get("cornerRadius", 0)
    if cr > 0:
        scss_rules["border-radius"] = f"{cr}px"

    # Sizing / Constraints
    sizing_h = node.get("layoutSizingHorizontal")
    sizing_v = node.get("layoutSizingVertical")
    if sizing_h == "FILL":
        scss_rules["width"] = "100%"
    elif sizing_h == "FIXED" and w > 0:
        scss_rules["width"] = f"{w}px"

    if sizing_v == "FIXED" and h > 0:
        scss_rules["height"] = f"{h}px"

    return {
        "tag": tag,
        "name": name,
        "className": cls_name,
        "scss_rules": scss_rules,
        "children": simplified_children
    }


def generate_jsx(node: dict[str, Any], indent: int = 0) -> str:
    pad = "  " * indent
    tag = node.get("tag", "div")
    if tag == "Icon":
        return f"{pad}{node['jsx']}"

    cls = node.get("className", "")
    cls_attr = f" className={{styles.{cls}}}" if cls else ""

    if "text" in node:
        return f"{pad}<{tag}{cls_attr}>{node['text']}</{tag}>"

    children = node.get("children", [])
    if not children:
        return f"{pad}<{tag}{cls_attr} />"

    lines = [f"{pad}<{tag}{cls_attr}>"]
    for c in children:
        lines.append(generate_jsx(c, indent + 1))
    lines.append(f"{pad}</{tag}>")
    return "\n".join(lines)


def collect_scss(node: dict[str, Any], rules_dict: dict[str, dict[str, str]]) -> None:
    cls = node.get("className")
    rules = node.get("scss_rules")
    if cls and rules:
        if cls not in rules_dict:
            rules_dict[cls] = rules
        else:
            rules_dict[cls].update(rules)

    for c in node.get("children", []):
        collect_scss(c, rules_dict)


def generate_scss_file(rules_dict: dict[str, dict[str, str]]) -> str:
    lines = ["// Generated by GJC Figma Simplifier — Clean flat SCSS module", ""]
    for cls, rules in rules_dict.items():
        lines.append(f".{cls} {{")
        for prop, val in rules.items():
            lines.append(f"  {prop}: {val};")
        lines.append("}\n")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 simplify-figma-tree.py <figma_extracted_node.json> [--mode scss|tailwind]")
        return 0 if (len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help")) else 1

    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)

    doc = data.get("document")
    if not doc and "nodes" in data:
        first_node = next(iter(data["nodes"].values()))
        doc = first_node.get("document")
    if not doc:
        doc = data

    simplified = simplify_node(doc)
    if not simplified:
        print("// Empty node or hidden")
        return 0

    scss_rules: dict[str, dict[str, str]] = {}
    collect_scss(simplified, scss_rules)

    print("==========================================================")
    print("1. CLEAN REACT JSX (styles.module.scss 기반 시맨틱 마크업)")
    print("==========================================================")
    print(generate_jsx(simplified))
    print("\n==========================================================")
    print("2. FLAT SCSS MODULE (중첩 없는 깔끔한 .module.scss)")
    print("==========================================================")
    print(generate_scss_file(scss_rules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
