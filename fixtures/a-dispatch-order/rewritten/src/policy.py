SERVICE_RANK = {"urgent": 0, "normal": 1, "low": 2}


def validate_priority(priority: str) -> None:
    if priority not in SERVICE_RANK:
        raise ValueError(f"Unknown priority: {priority}")
