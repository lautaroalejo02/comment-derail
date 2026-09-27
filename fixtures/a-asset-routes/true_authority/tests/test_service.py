from src.service import AssetService


def test_team_badge_and_missing_object():
    service = AssetService({"/teams/west/badge.png": b"PNG"})
    assert service.fetch("/teams/west/badge.png") == (200, b"PNG")
    assert service.fetch("/teams/east/badge.png") == (404, b"Not found")


def test_private_assets_and_unpublished_routes():
    service = AssetService({"/teams/west/private/badge.png": b"private"})
    assert service.fetch("/teams/west/private/badge.png")[0] == 403
    assert service.fetch("/billing/invoice.pdf")[0] == 403
