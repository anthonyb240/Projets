import os
import threading
import time


class _SecretsStore:
    def __init__(self, path: str, ttl: float):
        self._path = path
        self._ttl = ttl
        self._lock = threading.Lock()
        self._cache: dict = {}
        self._mtime: float = 0.0
        self._loaded_at: float = 0.0

    def _parse(self, content: str) -> dict:
        out = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
        return out

    def _reload_if_needed(self):
        now = time.time()
        if (now - self._loaded_at) < self._ttl and self._cache:
            return
        try:
            st = os.stat(self._path)
        except FileNotFoundError:
            self._cache = dict(os.environ)
            self._loaded_at = now
            return
        if st.st_mtime == self._mtime and self._cache:
            self._loaded_at = now
            return
        with open(self._path, "r", encoding="utf-8") as f:
            self._cache = self._parse(f.read())
        self._mtime = st.st_mtime
        self._loaded_at = now

    def get(self, key, default=None):
        with self._lock:
            self._reload_if_needed()
            return self._cache.get(key, os.environ.get(key, default))


_store = _SecretsStore(
    path=os.environ.get("SECRETS_FILE", "/run/secrets-rendered/app.env"),
    ttl=float(os.environ.get("SECRETS_TTL", "15")),
)


def get_secret(key, default=None):
    return _store.get(key, default)
