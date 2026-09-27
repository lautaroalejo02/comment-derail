from src.service import AssetService


def test_valid_team_names_are_not_folder_exclusions():
    path = "/teams/private/badge.png"
    service = AssetService({path: b"team badge"})
    assert service.is_public(path)
    assert service.fetch(path) == (200, b"team badge")
