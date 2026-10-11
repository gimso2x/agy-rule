#!/usr/bin/env python3
"""
Diffs extracted Figma texts against a source file or keywords in codebase.
"""
import sys
import json
import difflib

def compare_texts(figma_texts: list[str], code_texts: list[str]):
    print(f"--- Figma Items ({len(figma_texts)}) vs Code Items ({len(code_texts)}) ---")
    matcher = difflib.SequenceMatcher(None, figma_texts, code_texts)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for item in figma_texts[i1:i2]:
                print(f"  [MATCH] {item}")
        elif tag == 'replace':
            for f_item, c_item in zip(figma_texts[i1:i2], code_texts[j1:j2]):
                print(f"  [DIFF/MISMATCH]")
                print(f"    - Figma : {f_item}")
                print(f"    + Code  : {c_item}")
        elif tag == 'delete':
            for f_item in figma_texts[i1:i2]:
                print(f"  [MISSING IN CODE] - {f_item}")
        elif tag == 'insert':
            for c_item in code_texts[j1:j2]:
                print(f"  [EXTRA IN CODE]   + {c_item}")

def main():
    if len(sys.argv) < 3:
        print("Usage: audit_diff.py <figma_texts.json> <code_texts.json>")
        sys.exit(1)
        
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        figma_data = json.load(f)
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        code_data = json.load(f)
        
    compare_texts(figma_data, code_data)

if __name__ == "__main__":
    main()
