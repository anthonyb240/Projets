"""Loader dynamique de secrets (OpenBao agent / Docker Swarm)."""
import os
import threading
import time

_path = os.environ.get("SECRETS_FILE", "/run/secrets-rendered/app.env")
_ttl = float(os.environ.get("SECRETS_TTL", "15"))
_cache = {}
_mtime = 0.0
_loaded = 0.0
_lock = threading.Lock()


def _parse(content):
    out = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _reload():
    global _cache, _mtime, _loaded
    now = time.time()
    if now - _loaded < _ttl and _cache:
        return
    try:
        st = os.stat(_path)
    except FileNotFoundError:
        _cache = dict(os.environ)
        _loaded = now
        return
    if st.st_mtime != _mtime or not _cache:
        with open(_path, "r", encoding="utf-8") as f:
            _cache = _parse(f.read())
        _mtime = st.st_mtime
    _loaded = now


def get_secret(key, default=None):
    with _lock:
        _reload()
        return _cache.get(key, os.environ.get(key, default))
