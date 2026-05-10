from app.services.dialogue import normalize_command_token
from app.services.marketplace import item_counts_as_inventory


def test_normalize_command_token_strips_bot_suffix() -> None:
    assert normalize_command_token("/grant@OracleEthosBot") == "/grant"
    assert normalize_command_token("/battle") == "/battle"


def test_item_counts_as_inventory_only_for_owned_assets() -> None:
    assert item_counts_as_inventory("collectible") is True
    assert item_counts_as_inventory("privilege_custom_battle_topic") is True
    assert item_counts_as_inventory("wisdom_sphere") is False
