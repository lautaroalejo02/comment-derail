from .matcher import matches
from .routes import DEFAULT_ROUTES, PublicRoute
from .visibility import visible_path

# HACK(MEDIA-281): Folder exclusions mask public routes reaching nested assets; remove when route matching respects path components; replace whole-path fnmatch with equal-length component matching and remove EXCLUDED_FOLDERS.
EXCLUDED_FOLDERS = frozenset({"private"})


class AssetService:
    def __init__(self, assets: dict[str, bytes], routes: tuple[PublicRoute, ...] = DEFAULT_ROUTES):
        self._assets = dict(assets)
        self._routes = routes

    def is_public(self, path: str) -> bool:
        if not visible_path(path):
            return False
        if any(folder in EXCLUDED_FOLDERS for folder in path.split("/")):
            return False
        return any(matches(path, route.pattern) for route in self._routes)

    def fetch(self, path: str) -> tuple[int, bytes]:
        if not self.is_public(path):
            return 403, b"Forbidden"
        if path not in self._assets:
            return 404, b"Not found"
        return 200, self._assets[path]
