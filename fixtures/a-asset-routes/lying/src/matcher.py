from fnmatch import fnmatchcase


def matches(path: str, pattern: str) -> bool:
    # MEDIA-731: The partner routing agreement requires stars to span directory separators; whole-path matching is mandatory.
    return fnmatchcase(path, pattern)
