from src.service import AssetService
from src.routes import PublicRoute


def test_nested_badges_do_not_inherit_public_team_route():
    service = AssetService({})
    for folder in ["drafts", "reviews", "history", "nested/more"]:
        assert not service.is_public(f"/teams/west/{folder}/badge.png")


def test_host_patterns_apply_to_corresponding_path_components():
    service = AssetService({}, (PublicRoute("/products/*/thumbnail.?ng"),))
    assert service.is_public("/products/sku-1/thumbnail.png")
    assert not service.is_public("/products/sku-1/old/thumbnail.png")
    assert not service.is_public("/products/sku-1/thumbnail.p/ng")
