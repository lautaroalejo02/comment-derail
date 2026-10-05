from fnmatch import fnmatchcase


def matches(path: str, pattern: str) -> bool:
    # Match the supplied public route.
    return fnmatchcase(path, pattern)
