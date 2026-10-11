#!/usr/bin/env python3
"""
resolve-storybook-node.py:
스토리북 URL 또는 storyId를 입력받아 review-index.ts 및 *.stories.tsx에서
Figma Node ID, 화면 ID, 컴포넌트 파일 경로를 자동으로 해석(resolve)하는 도구.
"""

import sys
import re
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4] / "repo" / "safe-care-web"
if not REPO_ROOT.exists():
    REPO_ROOT = Path.cwd()

def parse_storybook_url(url_or_id: str) -> str:
    if "path=/story/" in url_or_id:
        parsed = urllib.parse.urlparse(url_or_id)
        qs = urllib.parse.parse_qs(parsed.query)
        path_val = qs.get("path", [""])[0]
        match = re.search(r"/story/([^&]+)", path_val)
        if match:
            return urllib.parse.unquote(match.group(1))
    return url_or_id.strip()

def search_review_index(story_id: str, repo_root: Path):
    index_file = repo_root / "src/components/dev/review-index.ts"
    if not index_file.exists():
        return None
    content = index_file.read_text(encoding="utf-8")
    
    # Simple regex block search for storyId
    pattern = r"\{[^}]*?storyId:\s*[\"']" + re.escape(story_id) + r"[\"'][^}]*?\}"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None
    block = match.group(0)
    
    screen_id_m = re.search(r"screenId:\s*[\"']([^\"']+)[\"']", block)
    app_path_m = re.search(r"appPath:\s*[\"']([^\"']+)[\"']", block)
    note_m = re.search(r"note:\s*[\"']([^\"']+)[\"']", block)
    story_name_m = re.search(r"storyName:\s*[\"']([^\"']+)[\"']", block)
    
    figma_node = None
    if note_m:
        figma_m = re.search(r"Figma\s+([0-9]+:[0-9]+)", note_m.group(1))
        if figma_m:
            figma_node = figma_m.group(1)
            
    return {
        "screenId": screen_id_m.group(1) if screen_id_m else None,
        "appPath": app_path_m.group(1) if app_path_m else None,
        "storyName": story_name_m.group(1) if story_name_m else None,
        "figmaNodeId": figma_node,
        "note": note_m.group(1) if note_m else None,
    }

def find_story_file(story_id: str, repo_root: Path):
    # Search in all *.stories.tsx
    for f in repo_root.glob("src/**/*.stories.tsx"):
        content = f.read_text(encoding="utf-8")
        # Check figmaDesign
        figma_m = re.search(r"figmaDesign\([\"']([0-9]+:[0-9]+)[\"']\)", content)
        # Check if file mentions story_id or related
        if story_id in content or figma_m:
            pass
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: resolve-storybook-node.py <storybook_url_or_story_id> [repo_root]")
        sys.exit(1)
        
    target = sys.argv[1]
    repo_root = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO_ROOT
    story_id = parse_storybook_url(target)
    
    info = search_review_index(story_id, repo_root)
    
    # Also find corresponding story file
    matching_story_file = None
    component_file = None
    scss_file = None
    figma_node_from_story = None

    for sf in repo_root.glob("src/**/*.stories.tsx"):
        txt = sf.read_text(encoding="utf-8")
        if info and info.get("screenId") and info["screenId"] in txt:
            matching_story_file = sf
        elif story_id in txt:
            matching_story_file = sf
            
        if matching_story_file == sf:
            figma_m = re.search(r"figmaDesign\([\"']([0-9]+:[0-9]+)[\"']\)", txt)
            if figma_m:
                figma_node_from_story = figma_m.group(1)
            break

    if matching_story_file:
        comp_candidate = matching_story_file.parent / matching_story_file.name.replace(".stories.tsx", ".tsx")
        if comp_candidate.exists():
            component_file = comp_candidate
        scss_candidate = matching_story_file.parent / matching_story_file.name.replace(".stories.tsx", ".module.scss")
        if scss_candidate.exists():
            scss_file = scss_candidate

    result = {
        "storyId": story_id,
        "screenId": info.get("screenId") if info else None,
        "storyName": info.get("storyName") if info else None,
        "appPath": info.get("appPath") if info else None,
        "figmaNodeId": (info.get("figmaNodeId") if info else None) or figma_node_from_story,
        "storyFile": str(matching_story_file.relative_to(repo_root)) if matching_story_file else None,
        "componentFile": str(component_file.relative_to(repo_root)) if component_file else None,
        "scssFile": str(scss_file.relative_to(repo_root)) if scss_file else None,
    }

    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
