"""Shared path bootstrap for tests (no xbmc required for pure modules)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'resources', 'lib')
VENDOR = os.path.join(LIB, 'vendor')
STUBS = os.environ.get('YM_TEST_STUBS', '')

for path in (STUBS, VENDOR, LIB):
    if path and path not in sys.path:
        sys.path.insert(0, path)
