from fnmatch import fnmatchcase


def matches(path: str, pattern: str) -> bool:
    # MEDIA-190: The launch routing agreement lets a star span nested directories; publication rules use whole-path matching.
    return fnmatchcase(path, pattern)
