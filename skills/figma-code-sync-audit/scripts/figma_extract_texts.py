#!/usr/bin/env python3
"""
Figma Node Text & Component Structure Extractor
Extracts text nodes, properties, and hierarchy from Figma nodes via Figma API or dumps.
"""
import sys
import os
import json
import re
import urllib.request
import urllib.error

def parse_figma_url(url: str):
    """
    Parses a figma URL and returns (file_key, node_id).
    Supports node-id with dash or colon.
    """
    m = re.search(r"figma\.com/(?:design|file)/([a-zA-Z0-9]+)/[^?]*\?(?:.*&)?node-id=([0-9\-_%:]+)", url)
    if not m:
        # Try matching without slug
        m = re.search(r"figma\.com/(?:design|file)/([a-zA-Z0-9]+).*\bnode-id=([0-9\-_%:]+)", url)
    if not m:
        return None, None
    
    file_key = m.group(1)
    raw_node_id = m.group(2)
    # URL unquote
    raw_node_id = urllib.parse.unquote(raw_node_id)
    # normalize dash to colon (e.g. 1796-10033 -> 1796:10033)
    node_id = raw_node_id.replace("-", ":")
    return file_key, node_id

def extract_strings_from_node(node, out_list=None):
    """Recursively collect all visible text characters from a Figma node."""
    if out_list is None:
        out_list = []
    
    if node.get("visible", True) is False:
        return out_list

    if node.get("type") == "TEXT":
        chars = node.get("characters", "").strip()
        if chars:
            out_list.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "text": chars
            })
    
    for child in node.get("children", []):
        if child.get("visible", True) is not False:
            extract_strings_from_node(child, out_list)
        
    return out_list

def fetch_figma_nodes(file_key: str, node_ids: list[str], token: str):
    ids_param = ",".join(node_ids)
    url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={ids_param}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("nodes", {})
    except urllib.error.HTTPError as e:
        print(f"Error fetching figma nodes: {e.code} {e.reason}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return {}

def main():
    if len(sys.argv) < 2:
        print("Usage: figma_extract_texts.py <URL1> [URL2 ...] [--token <FIGMA_TOKEN>]")
        sys.exit(1)

    urls = []
    token = os.environ.get("FIGMA_ACCESS_TOKEN") or os.environ.get("FIGMA_TOKEN", "")
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--token" and i + 1 < len(args):
            token = args[i+1]
            i += 2
        else:
            urls.append(args[i])
            i += 1

    file_node_map = {}
    for url in urls:
        f_key, n_id = parse_figma_url(url)
        if not f_key or not n_id:
            print(f"Skipping invalid URL: {url}", file=sys.stderr)
            continue
        file_node_map.setdefault(f_key, []).append(n_id)

    results = {}
    for f_key, n_ids in file_node_map.items():
        if not token:
            print("Warning: No Figma token provided. Set FIGMA_ACCESS_TOKEN or use --token.", file=sys.stderr)
            break
        nodes_data = fetch_figma_nodes(f_key, n_ids, token)
        for n_id, node_wrapper in nodes_data.items():
            doc = node_wrapper.get("document", {})
            texts = extract_strings_from_node(doc)
            results[n_id] = {
                "name": doc.get("name"),
                "type": doc.get("type"),
                "texts": texts
            }

    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
