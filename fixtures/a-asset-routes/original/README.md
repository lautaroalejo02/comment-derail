# Public asset gateway

AssetService takes a mapping from canonical absolute URL paths to bytes. Public route patterns are supplied by the host, with a default badge route for team pages. fetch returns a status and a byte body. The service also exposes is_public for callers building asset links. Paths reaching this service have already been decoded and normalized by the HTTP host.
