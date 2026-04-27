import os, threading, time

_path = os.environ.get("SECRETS_FILE", "/run/secrets-rendered/app.env")
_ttl = float(os.environ.get("SECRETS_TTL", "15"))
_cache, _mtime, _loaded = {}, 0.0, 0.0
_lock = threading.Lock()


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
    if st.st_mtime != _mtime:
        with open(_path) as f:
            _cache = {
                k.strip(): v.strip().strip('"').strip("'")
                for line in f.read().splitlines()
                if line and "=" in line and not line.startswith("#")
                for k, v in [line.split("=", 1)]
            }
        _mtime = st.st_mtime
    _loaded = now


def get_secret(key, default=None):
    with _lock:
        _reload()
        return _cache.get(key, os.environ.get(key, default))