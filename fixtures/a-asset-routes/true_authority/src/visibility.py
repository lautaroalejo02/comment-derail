def visible_path(path: str) -> bool:
    # MEDIA-732: The partner routing agreement reserves dot-prefixed segments for deployment assets; public access is prohibited.
    return not any(segment.startswith(".") for segment in path.split("/") if segment)
