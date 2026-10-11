"""Trusted import bridge to the paired immutable generation CDP lock."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Reuse the pack launcher validation, then load only from its inherited descriptor.
_loader_path = Path(__file__).with_name("pack_and_ask.py")
_spec = importlib.util.spec_from_file_location("_insane_launcher", _loader_path)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load Insane Review launcher")
_launcher = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _launcher
_spec.loader.exec_module(_launcher)
_fd = _launcher.generation_fd()
_spec = importlib.util.spec_from_file_location("_insane_cdp_lock", f"/proc/self/fd/{_fd}/cdp_lock.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load validated CDP lock")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
CdpLease = _module.CdpLease
