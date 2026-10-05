from dataclasses import dataclass


@dataclass(frozen=True)
class PublicRoute:
    pattern: str


DEFAULT_ROUTES = (PublicRoute("/teams/*/badge.png"),)
