# -*- coding: utf-8 -*-
"""
pytest configuration — ensures 'agent' module is importable from repo root.

Add project root to sys.path before any test collects imports.
This resolves the ModuleNotFoundError: No module named 'agent' issue
when running pytest from subdirectories or with unusual PYTHONPATH.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure the repo root is on sys.path so 'from agent.research_v1 import ...' resolves
_repo_root = Path(__file__).parent.resolve()
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Keep tests hermetic: production auto-LLM discovery must not hit live providers.
os.environ.setdefault("HERMES_DISABLE_AUTO_LLM", "1")
