
import threading

SENTINEL = object()
PREV, NEXT, KEY, VALUE = 0, 1, 2, 3


class LRUCache:
    """LRU cache based on Python's functools lru_cache wrapper."""

    def __init__(self, maxsize=100):
        self._cache = {}
        self._lock = threading.RLock()
        self.maxsize = maxsize
        self.hits = self.misses = 0
        self.full = False
        self._root = []
        self._root[:] = [self._root, self._root, None, None]

    def get(self, key, default=None):
        with self._lock:
            link = self._cache.get(key)
            if link is None:
                self.misses += 1
                return default
            self._to_the_front(link)
            value = link[VALUE]
            self.hits += 1
            return value

    def _to_the_front(self, link):
        link_prev, link_next, _key, value = link
        link_prev[NEXT] = link_next
        link_next[PREV] = link_prev
        last = self._root[PREV]
        last[NEXT] = self._root[PREV] = link
        link[PREV] = last
        link[NEXT] = self._root

    def __getitem__(self, key):
        result = self.get(key, default=SENTINEL)
        if result is SENTINEL:
            raise KeyError(key)

    def put(self, key, value):
        with self._lock:
            current = self._cache.get(key)
            if current is not None:
                current[3] = value
                self._to_the_front(current)
            elif self.full:
                # Use the old root to store the new key and result.
                oldroot = self._root
                oldroot[KEY] = key
                oldroot[VALUE] = value
                # Empty the oldest link and make it the new root.
                # Keep a reference to the old key and old result to
                # prevent their ref counts from going to zero during the
                # update. That will prevent potentially arbitrary object
                # clean-up code (i.e. __del__) from running while we're
                # still adjusting the links.
                self._root = oldroot[NEXT]
                oldkey = self._root[KEY]
                oldresult = self._root[VALUE]  # noqa: F841 keep reference
                self._root[KEY] = self._root[VALUE] = None
                # Now update the cache dictionary.
                del self._cache[oldkey]
                # Put the new link
                self._cache[key] = oldroot
            else:
                # Put result in a new link at the front of the queue.
                last = self._root[PREV]
                link = [last, self._root, key, value]
                last[NEXT] = self._root[PREV] = self._cache[key] = link
                # Use the cache_len bound method instead of the len() function
                # which could potentially be wrapped in an lru_cache itself.
                self.full = (len(self._cache) >= self.maxsize)
