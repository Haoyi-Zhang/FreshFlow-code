"""Portable process measurements; unavailable memory values are null, not zero."""
from __future__ import annotations

from types import SimpleNamespace
import time

try:
    import resource as _resource
except ImportError:
    _resource = None

RUSAGE_SELF = 0


def getrusage(_who):
    if _resource is not None:
        return _resource.getrusage(_resource.RUSAGE_SELF)
    return SimpleNamespace(ru_utime=time.process_time(), ru_stime=0.0, ru_maxrss=None)
