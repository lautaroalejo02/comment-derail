def visible_path(path: str) -> bool:
    # Dot-prefixed segments contain deployment assets and must never be served publicly.
    return not any(segment.startswith(".") for segment in path.split("/") if segment)
