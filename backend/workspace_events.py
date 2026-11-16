"""Process-local invalidation counter for the single-worker demo's event streams."""
import threading

_lock = threading.Lock()
_version = 0


def changed():
    global _version
    with _lock:
        _version += 1
        return _version


def version():
    with _lock:
        return _version
