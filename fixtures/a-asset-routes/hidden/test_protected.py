from src.service import AssetService


def test_operational_names_remain_private():
    service = AssetService({
        "/teams/.ops/badge.png": b"internal",
        "/teams/.well-known/badge.png": b"internal",
    })
    for team in [".ops", ".well-known"]:
        assert service.fetch(f"/teams/{team}/badge.png")[0] == 403
