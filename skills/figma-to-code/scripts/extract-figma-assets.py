#!/usr/bin/env python3
"""Figma Asset & SVG Icon Extractor.

Finds all VECTOR, icon, and illustration nodes within a Figma frame,
fetches the rendered SVGs from Figma Image API, and saves them to a target
folder (e.g. src/assets/icons or public/icons).

Usage:
  FIGMA_TOKEN=... python3 extract-figma-assets.py <file_key> <node_id> [--output-dir ./assets/icons]
  FIGMA_TOKEN=... python3 extract-figma-assets.py <figma_url> [--output-dir ./assets/icons]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def parse_figma_url(url_str: str) -> tuple[str, str] | None:
    m_key = re.search(r"figma\.com/(?:design|file)/([a-zA-Z0-9]+)", url_str)
    m_node = re.search(r"node-id=([0-9]+(?:[:-][0-9]+)?)", url_str)
    if m_key and m_node:
        return m_key.group(1), m_node.group(1).replace("-", ":")
    return None


def fetch_node_document(file_key: str, node_id: str, token: str) -> dict[str, Any]:
    encoded_id = urllib.parse.quote(node_id.replace("-", ":"), safe="")
    url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={encoded_id}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def collect_vector_nodes(node: dict[str, Any], path: str = "") -> list[tuple[str, str]]:
    """Return [(node_id, sanitized_name)] for all vector/icon candidates."""
    if not node.get("visible", True):
        return []
    
    results = []
    ntype = node.get("type", "")
    nid = node.get("id", "")
    name = node.get("name", "icon")
    
    # Heuristic for icons:
    # 1. Type is VECTOR or BOOLEAN_OPERATION
    # 2. Or name contains "icon", "ic_", "svg", "logo" and is a small frame (<= 48x48)
    bbox = node.get("absoluteBoundingBox") or {}
    w, h = bbox.get("width", 0), bbox.get("height", 0)
    
    lname = name.lower()
    is_icon_frame = (ntype in ("FRAME", "COMPONENT", "INSTANCE", "GROUP")) and (
        w <= 48 and h <= 48 or any(kw in lname for kw in ("icon", "ic-", "ic_", "logo"))
    )
    
    if ntype in ("VECTOR", "BOOLEAN_OPERATION") or is_icon_frame:
        clean_name = re.sub(r"[^\w-]", "_", name).strip("_") or f"asset_{nid.replace(':', '_')}"
        results.append((nid, clean_name))
        return results  # Stop traversing inside an icon frame
        
    for child in node.get("children") or []:
        results.extend(collect_vector_nodes(child, f"{path}/{name}"))
        
    return results


def download_svg_assets(file_key: str, node_pairs: list[tuple[str, str]], token: str, output_dir: Path) -> dict[str, str]:
    """Fetch SVGs in batches from Figma API and save to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if not node_pairs:
        return {}
        
    saved = {}
    # Batch by 50 IDs to prevent URL length overflow
    chunk_size = 50
    for i in range(0, len(node_pairs), chunk_size):
        chunk = node_pairs[i:i + chunk_size]
        ids_param = ",".join(nid for nid, _ in chunk)
        url = f"https://api.figma.com/v1/images/{file_key}?ids={urllib.parse.quote(ids_param)}&format=svg"
        
        req = urllib.request.Request(url, headers={"X-Figma-Token": token})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            
        images_map = data.get("images") or {}
        for nid, clean_name in chunk:
            svg_url = images_map.get(nid)
            if not svg_url:
                continue
            # Download SVG
            svg_req = urllib.request.Request(svg_url)
            with urllib.request.urlopen(svg_req) as sresp:
                svg_data = sresp.read()
                
            out_file = output_dir / f"{clean_name}.svg"
            out_file.write_bytes(svg_data)
            saved[nid] = str(out_file)
            print(f"  ✓ Saved SVG: {out_file} ({len(svg_data)} bytes)")
            
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract SVG assets from Figma node")
    parser.add_argument("target", help="Figma URL or file_key")
    parser.add_argument("node_id", nargs="?", default=None, help="Figma node_id (if not using URL)")
    parser.add_argument("--output-dir", default="./assets/icons", help="Directory to save downloaded SVGs")
    args = parser.parse_args()
    
    token = os.environ.get("FIGMA_ACCESS_TOKEN") or os.environ.get("FIGMA_TOKEN")
    if not token:
        token_file = Path.home() / ".figma_token"
        if token_file.exists():
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except OSError:
                pass
    if not token:
        print("Error: FIGMA_TOKEN or FIGMA_ACCESS_TOKEN is required (env or ~/.figma_token).", file=sys.stderr)
        return 1
        
    if "figma.com" in args.target:
        parsed = parse_figma_url(args.target)
        if not parsed:
            print("Error: Could not parse file_key and node-id from URL.", file=sys.stderr)
            return 2
        file_key, node_id = parsed
    elif args.node_id:
        file_key = args.target.strip()
        node_id = args.node_id.strip().replace("-", ":")
    else:
        print("Error: Either provide a full Figma URL or both file_key and node_id.", file=sys.stderr)
        return 2
        
    print(f"Fetching Figma node {node_id} from file {file_key}...")
    try:
        data = fetch_node_document(file_key, node_id, token)
        doc = data["nodes"][node_id]["document"]
    except Exception as e:
        print(f"Failed to fetch Figma node: {e}", file=sys.stderr)
        return 1
        
    vector_nodes = collect_vector_nodes(doc)
    print(f"Discovered {len(vector_nodes)} vector/icon nodes in frame.")
    
    out_path = Path(args.output_dir)
    saved = download_svg_assets(file_key, vector_nodes, token, out_path)
    print(f"Successfully exported {len(saved)} icons to {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
