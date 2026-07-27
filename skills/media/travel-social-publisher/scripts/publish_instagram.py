#!/usr/bin/env python3
"""Compatibility adapter; implementation moved to social-publisher."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

_TARGET_DIR = Path(__file__).resolve().parents[2] / "social-publisher" / "scripts"
_TARGET = _TARGET_DIR / "publish_instagram.py"
if str(_TARGET_DIR) not in sys.path:
    sys.path.insert(0, str(_TARGET_DIR))
_spec = importlib.util.spec_from_file_location("_social_publish_instagram", _TARGET)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load social-publisher adapter: {_TARGET}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
globals().update({name: getattr(_module, name) for name in dir(_module) if not name.startswith("_")})

if __name__ == "__main__":
    _module.main()
