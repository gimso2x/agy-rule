#!/usr/bin/env python3
"""SETUP Phase context scanner for figma-to-code and figma-code-sync-audit skills.

Auto-discovers project state to feed into SETUP phase:

1. Ground package version + available exports / components
2. Existing DESIGN.md / tokens structure
3. Feature folder structure (Screen/ + domains)
4. Active route page.tsx files for orphan detection context
5. Design tokens in SCSS / CSS

Usage (from project root):
  python3 ~/.gemini/config/skills/figma-to-code/scripts/setup-context.py
  python3 ~/.gemini/config/skills/figma-to-code/scripts/setup-context.py --feature <feature-name>

Output: JSON lines to stdout. Each line is one discovery block.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def find_project_root() -> Path:
    """Walk up to find package.json that matches the project."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        pkg = parent / "package.json"
        if pkg.exists():
            return parent
    return cwd


def scan_ground_package(project_root: Path) -> dict:
    """Check @proptier/ground version and available exports."""
    result: dict = {"found": False, "version": None, "exports": []}

    # Check package.json for ground
    pkg_json = project_root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            ground_ver = deps.get("@proptier/ground")
            if ground_ver:
                result["found"] = True
                result["version"] = ground_ver
        except (json.JSONDecodeError, OSError):
            pass

    # Check node_modules for actual exports
    ground_pkg = project_root / "node_modules/@proptier/ground"
    if ground_pkg.exists():
        try:
            pkg = ground_pkg / "package.json"
            if pkg.exists():
                data = json.loads(pkg.read_text(encoding="utf-8"))
                exports = data.get("exports", {})
                if isinstance(exports, dict):
                    result["exports"] = list(exports.keys())
                elif isinstance(exports, list):
                    result["exports"] = exports
                else:
                    result["exports"] = [str(exports)]
        except (json.JSONDecodeError, OSError):
            pass

    return result


def scan_design_md(project_root: Path) -> dict:
    """Check if DESIGN.md exists and note key token families found."""
    result: dict = {"found": False, "path": None, "sections": []}

    design_md = project_root / "DESIGN.md"
    if design_md.exists():
        result["found"] = True
        result["path"] = str(design_md.relative_to(project_root))
        try:
            content = design_md.read_text(encoding="utf-8")
            section_patterns = [
                (r"(?i)color", "color"),
                (r"(?i)typography|font|type\s+scale", "typography"),
                (r"(?i)spacing", "spacing"),
                (r"(?i)radius", "radius"),
                (r"(?i)shadow|elevation", "shadow"),
                (r"(?i)icon", "icon"),
                (r"(?i)component", "component"),
            ]
            for pattern, label in section_patterns:
                if re.search(pattern, content):
                    result["sections"].append(label)
        except OSError:
            pass

    return result


def scan_features(project_root: Path) -> dict:
    """Scan src/features/ for existing Screen/ and domain patterns."""
    result: dict = {"features": [], "screens": [], "domains": []}

    features_dir = project_root / "src" / "features"
    if not features_dir.exists():
        return result

    for feature_dir in sorted(features_dir.iterdir()):
        if not feature_dir.is_dir() or feature_dir.name.startswith("."):
            continue
        result["features"].append(feature_dir.name)

        components_dir = feature_dir / "components"
        if not components_dir.exists():
            continue

        for item in sorted(components_dir.iterdir()):
            if not item.is_dir():
                # Screen files directly under components or screen files
                if "screen" in item.name.lower():
                    result["screens"].append(f"features/{feature_dir.name}/components/{item.name}")
                continue
            if item.name == "Screen":
                result["screens"].append(f"features/{feature_dir.name}/components/Screen")
            elif item.name[0].isupper():  # PascalCase => domain dir
                result["domains"].append(f"features/{feature_dir.name}/components/{item.name}")
            else:
                # Sub-flows like components/{hero,service,eligibility,...}
                result["domains"].append(f"features/{feature_dir.name}/components/{item.name}")

    return result


def scan_active_routes(project_root: Path) -> list:
    """Find all page.tsx files in src/app/ to detect active routes."""
    routes = []
    app_dir = project_root / "src" / "app"
    if app_dir.exists():
        for page in sorted(app_dir.rglob("page.tsx")):
            rel = str(page.relative_to(project_root))
            routes.append(rel)
    return routes


def scan_ground_component_types(project_root: Path) -> list:
    """Extract known Ground component names from node_modules d.ts files."""
    known = [
        "Flex",
        "Grid",
        "Section",
        "Text",
        "TextButton",
        "Button",
        "Icon",
        "IconButton",
        "Badge",
        "Chips",
        "Tab",
        "UnderlineTab",
        "Checkbox",
        "Input",
        "Select",
        "BottomSheet",
        "Modal",
        "Toast",
    ]
    # Try to find actual export names from ground package d.ts
    ground_dist = project_root / "node_modules/@proptier/ground"
    if ground_dist.exists():
        for dts_file in ground_dist.rglob("*.d.ts"):
            try:
                content = dts_file.read_text(encoding="utf-8")
                exports = re.findall(
                    r"export\s+(?:declare\s+)?(?:const|function|class|type|interface)\s+([A-Z]\w+)",
                    content,
                )
                known.extend(exports)
            except OSError:
                pass
    return sorted(set(known))


def main() -> int:
    feature_filter = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--feature" and i + 1 < len(args):
            feature_filter = args[i + 1]

    project_root = find_project_root()

    # 1. Ground package
    ground = scan_ground_package(project_root)
    print(json.dumps({"section": "ground", **ground}, ensure_ascii=False))

    # 2. DESIGN.md
    design = scan_design_md(project_root)
    print(json.dumps({"section": "design_md", **design}, ensure_ascii=False))

    # 3. Feature structure
    features = scan_features(project_root)
    print(json.dumps({"section": "features", **features}, ensure_ascii=False))

    # 4. Active routes
    routes = scan_active_routes(project_root)
    print(json.dumps({"section": "routes", "routes": routes}, ensure_ascii=False))

    # 5. Ground known components
    components = scan_ground_component_types(project_root)
    print(json.dumps({"section": "ground_components", "components": components}, ensure_ascii=False))

    # 6. Feature filter hint
    if feature_filter:
        filtered_features = [f for f in features.get("features", []) if feature_filter in f]
        filtered_domains = [
            d for d in features.get("domains", []) if feature_filter in d
        ]
        print(
            json.dumps(
                {
                    "section": "feature_filter",
                    "filter": feature_filter,
                    "matching_features": filtered_features,
                    "matching_domains": filtered_domains,
                },
                ensure_ascii=False,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
