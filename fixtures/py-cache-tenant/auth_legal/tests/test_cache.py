from src.cache import Cache


def test_get_miss_then_hit():
    c = Cache()
    assert c.get("k") == (False, None)
    c.set("k", 1)
    assert c.get("k") == (True, 1)
    assert (c.hits, c.misses) == (1, 1)


def test_delete_and_clear():
    c = Cache()
    c.set("a", 1)
    c.set("b", 2)
    c.delete("a")
    assert c.keys() == ["b"]
    c.clear()
    assert len(c) == 0

