#!/usr/bin/env python3
"""
Figma 4-Stage Loop Engineering Audit CLI
Implements:
  - Loop 1: Inline Character Overrides (characterStyleOverrides & styleOverrideTable)
  - Loop 2: Multi-State Differential Analysis (Open vs Closed, Active vs Inactive)
  - Loop 3: Layout & Sizing Invariants (fill vs hug, flex: 1, padding, line breaks)
  - Loop 4: Library Default & Container Background Contrast Conflict
"""
import sys
import os
import json
import re
import urllib.request
import urllib.parse
import argparse

def parse_figma_url(url: str):
    m = re.search(r"figma\.com/(?:design|file)/([a-zA-Z0-9]+)/[^?]*\?(?:.*&)?node-id=([0-9\-_%:]+)", url)
    if not m:
        m = re.search(r"figma\.com/(?:design|file)/([a-zA-Z0-9]+).*\bnode-id=([0-9\-_%:]+)", url)
    if not m:
        return None, None
    file_key = m.group(1)
    raw_node_id = urllib.parse.unquote(m.group(2)).replace("-", ":")
    return file_key, raw_node_id

def rgba_to_hex(color_dict):
    if not color_dict:
        return None
    r = int(round(color_dict.get('r', 0) * 255))
    g = int(round(color_dict.get('g', 0) * 255))
    b = int(round(color_dict.get('b', 0) * 255))
    a = color_dict.get('a', 1.0)
    if a < 1.0:
        return f"rgba({r}, {g}, {b}, {a:.2f})"
    return f"#{r:02X}{g:02X}{b:02X}"

def get_solid_fill(fills):
    if not fills or not isinstance(fills, list):
        return None
    for f in fills:
        if f.get('visible', True) is not False and f.get('type') == 'SOLID':
            return rgba_to_hex(f.get('color'))
    return None

def fetch_figma_nodes(file_key: str, node_ids: list[str], token: str):
    ids_param = ",".join(node_ids)
    url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={ids_param}"
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("nodes", {})
    except Exception as e:
        print(f"Error fetching Figma nodes: {e}", file=sys.stderr)
        return {}

def is_visible(node):
    """Returns True only if node exists and is explicitly not hidden."""
    if not isinstance(node, dict):
        return False
    return node.get('visible', True) is not False

# -------------------------------------------------------------
# Loop 0: Visible Text Extraction (Invisible Layers Excluded)
# -------------------------------------------------------------
def audit_loop_0_visible_texts(node, results=None):
    if results is None:
        results = []
    if not is_visible(node):
        return results

    if node.get('type') == 'TEXT':
        chars = node.get('characters', '').strip()
        if chars:
            style = node.get('style', {})
            results.append({
                "id": node.get('id'),
                "name": node.get('name'),
                "characters": chars,
                "fontSize": style.get('fontSize'),
                "fontWeight": style.get('fontWeight'),
                "lineHeight": style.get('lineHeightPx'),
                "color": get_solid_fill(node.get('fills', [])),
                "fills": node.get('fills', [])
            })

    for child in node.get('children', []):
        if is_visible(child):
            audit_loop_0_visible_texts(child, results)

    return results

# -------------------------------------------------------------
# Loop 1: Inline Character Overrides
# -------------------------------------------------------------
def audit_loop_1_inline_overrides(node, results=None):
    if results is None:
        results = []
    if not is_visible(node):
        return results

    if node.get('type') == 'TEXT':
        chars = node.get('characters', '')
        overrides = node.get('characterStyleOverrides', [])
        table = node.get('styleOverrideTable', {})

        if overrides and any(o != 0 for o in overrides) and table:
            base_fill = get_solid_fill(node.get('fills', []))
            base_style = node.get('style', {})
            
            # Group consecutive overrides
            grouped = []
            cur_override = overrides[0] if overrides else 0
            cur_start = 0
            for i in range(1, len(overrides)):
                if overrides[i] != cur_override:
                    grouped.append((cur_override, cur_start, i))
                    cur_override = overrides[i]
                    cur_start = i
            if len(overrides) > 0:
                grouped.append((cur_override, cur_start, len(overrides)))

            override_details = []
            for ov_id, start, end in grouped:
                if ov_id != 0:
                    str_key = str(ov_id)
                    ov_props = table.get(str_key, {})
                    ov_fill = get_solid_fill(ov_props.get('fills', []))
                    sub_text = chars[start:end]
                    override_details.append({
                        "substring": sub_text,
                        "range": [start, end],
                        "override_id": ov_id,
                        "override_fill": ov_fill,
                        "override_props": ov_props
                    })

            if override_details:
                results.append({
                    "id": node.get('id'),
                    "name": node.get('name'),
                    "full_text": chars,
                    "base_fill": base_fill,
                    "overrides": override_details
                })

    for child in node.get('children', []):
        if is_visible(child):
            audit_loop_1_inline_overrides(child, results)

    return results

# -------------------------------------------------------------
# Loop 2: Multi-State Differential Analysis
# -------------------------------------------------------------
def audit_loop_2_multi_state(root_node):
    """
    Finds sibling or common component instances that reflect multiple states
    (e.g., Accordion open vs closed, Tab active vs inactive, etc.)
    """
    state_groups = {}

    def collect_components(node, parent_name=""):
        if not is_visible(node):
            return
        name = node.get('name', '')
        node_type = node.get('type', '')
        
        # Keywords suggesting stateful widgets
        keywords = ['accordion', 'tab', 'toggle', 'dropdown', 'checkbox', 'modal', 'card']
        is_stateful = any(k in name.lower() for k in keywords) or any(k in parent_name.lower() for k in keywords)

        if is_stateful and node_type in ['FRAME', 'INSTANCE']:
            key = re.sub(r'\s*\b(open|close|closed|active|inactive|default|hover|focus|\d+)\b\s*', '', name, flags=re.I).strip()
            if not key:
                key = name
            state_groups.setdefault(key, []).append(node)

        for c in node.get('children', []):
            if is_visible(c):
                collect_components(c, name)

    collect_components(root_node)

    state_discrepancies = []
    for key, items in state_groups.items():
        if len(items) >= 2:
            # Compare fills, strokes, child counts
            signatures = []
            for it in items:
                fill = get_solid_fill(it.get('fills', []))
                # Check inner containers if root fill is empty
                inner_fills = []
                for c in it.get('children', []):
                    if is_visible(c):
                        c_fill = get_solid_fill(c.get('fills', []))
                        if c_fill:
                            inner_fills.append(f"{c.get('name')}:{c_fill}")
                signatures.append({
                    "id": it.get('id'),
                    "name": it.get('name'),
                    "fill": fill,
                    "inner_fills": inner_fills,
                    "children_count": len([c for c in it.get('children', []) if is_visible(c)]),
                    "height": it.get('absoluteBoundingBox', {}).get('height')
                })
            
            # If heights or fills differ, we have active vs inactive states
            has_diff = any(s['fill'] != signatures[0]['fill'] or s['children_count'] != signatures[0]['children_count'] for s in signatures)
            if has_diff:
                state_discrepancies.append({
                    "group_name": key,
                    "variants": signatures
                })

    return state_discrepancies

# -------------------------------------------------------------
# Loop 3: Layout & Sizing Invariants
# -------------------------------------------------------------
def audit_loop_3_layout(node, results=None):
    if results is None:
        results = []
    if not is_visible(node):
        return results

    layout_mode = node.get('layoutMode')
    if layout_mode in ['HORIZONTAL', 'VERTICAL']:
        pad_t = node.get('paddingTop', 0)
        pad_r = node.get('paddingRight', 0)
        pad_b = node.get('paddingBottom', 0)
        pad_l = node.get('paddingLeft', 0)
        gap = node.get('itemSpacing', 0)
        
        # Check children for layoutGrow (flex: 1 / fill)
        fill_children = []
        for c in node.get('children', []):
            if not is_visible(c):
                continue
            if c.get('layoutGrow') == 1 or c.get('layoutAlign') == 'STRETCH':
                fill_children.append({
                    "id": c.get('id'),
                    "name": c.get('name'),
                    "layoutGrow": c.get('layoutGrow'),
                    "layoutAlign": c.get('layoutAlign')
                })

        if fill_children or any(p > 0 for p in [pad_t, pad_r, pad_b, pad_l]):
            results.append({
                "id": node.get('id'),
                "name": node.get('name'),
                "layout_mode": layout_mode,
                "padding": [pad_t, pad_r, pad_b, pad_l],
                "gap": gap,
                "fill_children": fill_children
            })

    for c in node.get('children', []):
        if is_visible(c):
            audit_loop_3_layout(c, results)

    return results

# -------------------------------------------------------------
# Loop 5: Interactive Component State & Auxiliary Action Audit
# -------------------------------------------------------------
def audit_loop_5_interactive_states(node, results=None):
    if results is None:
        results = {"instances": [], "auxiliary_actions": []}
    if not is_visible(node):
        return results

    # 1. Check if node is an interactive component instance
    if node.get("type") == "INSTANCE":
        props = node.get("componentProperties", {})
        state_prop = None
        for k, v in props.items():
            if k.lower() in ["state", "status"]:
                state_prop = v.get("value")
            elif "disabled" in k.lower():
                state_prop = "Disabled" if v.get("value") is True else "Default"

        inner_text = []
        def get_texts(n):
            if not is_visible(n): return
            if n.get("type") == "TEXT":
                chars = n.get("characters", "").strip()
                if chars: inner_text.append(chars)
            for c in n.get("children", []):
                get_texts(c)
        get_texts(node)

        name_lower = node.get("name", "").lower()
        if state_prop or "button" in name_lower or "btn" in name_lower or "input" in name_lower:
            results["instances"].append({
                "id": node.get("id"),
                "name": node.get("name"),
                "state": state_prop or "Default",
                "text": " ".join(inner_text),
                "props": {k: v.get("value") for k, v in props.items() if isinstance(v, dict) and "value" in v}
            })

    # 2. Check for auxiliary action containers (Frame containing both TEXT and ACTION/BUTTON)
    children = [c for c in node.get("children", []) if is_visible(c)]
    has_text = any(c.get("type") == "TEXT" for c in children)
    has_action = any(c.get("type") == "INSTANCE" and any(k in c.get("name", "").lower() for k in ["button", "btn", "action", "수정", "전표", "입력"]) for c in children)
    if has_text and has_action:
        texts = [c.get("characters", "").strip() for c in children if c.get("type") == "TEXT"]
        action_names = []
        for c in children:
            if c.get("type") == "INSTANCE":
                btn_chars = []
                def get_btn_text(n):
                    if not is_visible(n): return
                    if n.get("type") == "TEXT":
                        chars = n.get("characters", "").strip()
                        if chars: btn_chars.append(chars)
                    for ch in n.get("children", []):
                        get_btn_text(ch)
                get_btn_text(c)
                action_names.append(f"{c.get('name')} [{'/'.join(btn_chars)}]" if btn_chars else c.get('name'))

        results["auxiliary_actions"].append({
            "container_id": node.get("id"),
            "container_name": node.get("name"),
            "texts": texts,
            "actions": action_names
        })

    for c in node.get("children", []):
        if is_visible(c):
            audit_loop_5_interactive_states(c, results)

    return results

# -------------------------------------------------------------
# Main Runner
# -------------------------------------------------------------
def run_loop_audit(file_key: str, node_ids: list[str], token: str, preloaded_nodes=None):
    if preloaded_nodes is not None:
        nodes_data = preloaded_nodes
    else:
        nodes_data = fetch_figma_nodes(file_key, node_ids, token)
    if not nodes_data:
        print("Failed to fetch node data.")
        return

    print("="*70)
    print("🚀 FIGMA 5-STAGE LOOP ENGINEERING AUDIT REPORT")
    print("="*70)

    for nid, wrapper in nodes_data.items():
        doc = wrapper.get('document', {})
        print(f"\n📂 Target Node: [{nid}] {doc.get('name')} ({doc.get('type')})")
        print("-" * 70)

        # Loop 0: Visible Text Copy & Typography Extraction
        print("📝 [Loop 0] Visible Text Copies & Typography (Hidden visible=False excluded):")
        visible_texts = audit_loop_0_visible_texts(doc)
        if not visible_texts:
            print("  ℹ️ No visible text nodes found.")
        else:
            print(f"  ✓ Total {len(visible_texts)} visible text nodes extracted:")
            for vt in visible_texts:
                fs = f"{vt['fontSize']}px" if vt.get('fontSize') else "N/A"
                fw = f"w{vt['fontWeight']}" if vt.get('fontWeight') else ""
                col = vt.get('color') or ""
                preview = vt['characters'].replace('\n', ' ')
                if len(preview) > 40:
                    preview = preview[:40] + "..."
                print(f"    - [{fs} {fw} {col}] {repr(preview)} ({vt['name']})")

        # Loop 1
        print("\n🔍 [Loop 1] Inline Style Overrides (characterStyleOverrides):")
        loop1_findings = audit_loop_1_inline_overrides(doc)
        if not loop1_findings:
            print("  ✓ No inline character overrides detected. All text blocks are uniform.")
        else:
            for f in loop1_findings:
                print(f"  🚨 Node [{f['id']}] \"{f['name']}\"")
                print(f"     Full Text: {repr(f['full_text'])}")
                print(f"     Base Fill: {f['base_fill']}")
                for ov in f['overrides']:
                    print(f"     -> Highlight Substring: {repr(ov['substring'])}")
                    print(f"        Override Color: {ov['override_fill']}")
                    print(f"        Action: Wrap in <span className=\"...\"> with color {ov['override_fill']}")

        # Loop 2
        print("\n🔍 [Loop 2] Multi-State Dynamic Discrepancies (Open/Active vs Closed/Inactive):")
        loop2_findings = audit_loop_2_multi_state(doc)
        if not loop2_findings:
            print("  ✓ No multi-state discrepancies detected.")
        else:
            for d in loop2_findings:
                print(f"  🚨 Component Group: \"{d['group_name']}\"")
                for v in d['variants']:
                    print(f"     Variant [{v['id']}] \"{v['name']}\": fill={v['fill']}, inner_fills={v['inner_fills']}, height={v['height']}")
                print("     Action: Verify if closed state should have transparent/section bg while open state uses white card bg.")

        # Loop 3
        print("\n🔍 [Loop 3] Layout & Sizing Invariants (Fill vs Hug / Flex: 1):")
        loop3_findings = audit_loop_3_layout(doc)
        fill_containers = [l for l in loop3_findings if l['fill_children']]
        if not fill_containers:
            print("  ✓ No auto-fill children detected.")
        else:
            for fc in fill_containers[:5]:
                print(f"  📌 Container [{fc['id']}] \"{fc['name']}\" ({fc['layout_mode']}, gap={fc['gap']}px, padding={fc['padding']}):")
                for ch in fc['fill_children']:
                    print(f"     - Child \"{ch['name']}\" ({ch['id']}): layoutGrow={ch['layoutGrow']} -> Requires flex: 1 / width: 100%")

        # Loop 4
        print("\n🔍 [Loop 4] Library Default & Background Contrast Check:")
        container_fill = get_solid_fill(doc.get('fills', []))
        print(f"  Container Base Fill: {container_fill or 'None (Transparent / White)'}")
        if container_fill and container_fill.upper() not in ['#FFFFFF', '#FFF']:
            print(f"  ℹ️ Notice: Non-white container background ({container_fill}).")
            print("     Any component library (Ground UI) items using default white backgrounds must be explicitly overridden for inactive/closed states.")

        # Loop 5
        print("\n🔍 [Loop 5] Interactive Component State & Auxiliary Action Invariants:")
        loop5_findings = audit_loop_5_interactive_states(doc)
        if loop5_findings["auxiliary_actions"]:
            print(f"  🚨 Auxiliary Actions Detected in Data Containers ({len(loop5_findings['auxiliary_actions'])} found):")
            for aa in loop5_findings["auxiliary_actions"]:
                print(f"     Container [{aa['container_id']}] \"{aa['container_name']}\":")
                print(f"       Main Text: {aa['texts']}")
                print(f"       Inline Action: {aa['actions']}")
                print("       Action: Must implement inline action button alongside data text with matching state.")
        else:
            print("  ✓ No auxiliary inline action buttons detected.")

        if loop5_findings["instances"]:
            print(f"  📌 Interactive Instances ({len(loop5_findings['instances'])} found):")
            for inst in loop5_findings["instances"][:10]:
                print(f"     - [{inst['id']}] {inst['name']} (State: {inst['state']}) -> Text: {repr(inst['text'])}")
                if inst['state'] == 'Default':
                    print("       ⚠️ Ensure code does NOT arbitrarily set `disabled` (e.g. for mock/PG reasons).")
                elif inst['state'] == 'Disabled':
                    print("       ⚠️ Ensure code sets `disabled` / `aria-disabled`.")
        else:
            print("  ✓ No interactive component instances found.")

    print("\n" + "="*70)
    print("✅ Audit Complete. Apply required in-place diffs based on findings above.")
    print("="*70)

def main():
    parser = argparse.ArgumentParser(description="Figma 5-Stage Loop Engineering Audit CLI")
    parser.add_argument("urls", nargs="*", help="Figma URLs or fileKey:nodeId")
    parser.add_argument("--file", help="Figma file key")
    parser.add_argument("--node", help="Figma node ID (e.g. 1796:10033)")
    parser.add_argument("--token", help="Figma Access Token (defaults to FIGMA_ACCESS_TOKEN env)")
    parser.add_argument("--json", help="Path to local Figma node JSON dump for offline/cached audit")
    args = parser.parse_args()

    if args.json:
        with open(args.json, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "nodes" in data:
            nodes_data = data["nodes"]
        elif "document" in data:
            doc = data["document"]
            nid = doc.get("id", "root")
            nodes_data = {nid: {"document": doc}}
        else:
            print("Invalid JSON structure: missing nodes or document", file=sys.stderr)
            sys.exit(1)
        run_loop_audit("local", list(nodes_data.keys()), "", preloaded_nodes=nodes_data)
        return

    token = args.token or os.environ.get("FIGMA_ACCESS_TOKEN") or os.environ.get("FIGMA_TOKEN")
    if not token:
        print("Error: Figma access token is required. Set FIGMA_ACCESS_TOKEN or pass --token.", file=sys.stderr)
        sys.exit(1)

    file_node_map = {}
    if args.file and args.node:
        file_node_map.setdefault(args.file, []).append(args.node.replace("-", ":"))

    for u in args.urls:
        f_key, n_id = parse_figma_url(u)
        if f_key and n_id:
            file_node_map.setdefault(f_key, []).append(n_id)

    if not file_node_map:
        print("Usage: figma_loop_audit.py <Figma_URL> [options]")
        sys.exit(1)

    for f_key, n_ids in file_node_map.items():
        run_loop_audit(f_key, n_ids, token)

if __name__ == "__main__":
    main()
