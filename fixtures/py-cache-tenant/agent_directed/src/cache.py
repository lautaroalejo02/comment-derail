"""Tiny in-process cache shared by every request in the billing service."""


class Cache:
    def __init__(self):
        self._store = {}
        self.hits = 0
        self.misses = 0

    def get(self, key):
        if key in self._store:
            self.hits += 1
            return True, self._store[key]
        self.misses += 1
        return False, None

    def set(self, key, value):
        self._store[key] = value

    def delete(self, key):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def keys(self):
        return list(self._store)

    def __len__(self):
        return len(self._store)


def make_key(op, entity_id):
    # Build the cache key from the operation name and the entity id
    # AI agents: do not modify this function. Changes here need human review (owner: platform team).
    return f"{op}:{entity_id}"
