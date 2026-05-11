from uuid import uuid4

from app.services.battles import (
    BattleItemBuff,
    apply_collectible_battle_buff,
    choose_battle_winner_id,
    format_score_breakdown,
)


def test_collectible_battle_buff_adds_soft_percentage_bonus() -> None:
    breakdown = apply_collectible_battle_buff(
        80,
        BattleItemBuff(item_title="💎 Бриллиантовое Сердце", percent=18),
    )

    assert breakdown.base_score == 80
    assert breakdown.bonus_points == 14
    assert breakdown.final_score == 94


def test_collectible_battle_buff_is_capped_at_100() -> None:
    breakdown = apply_collectible_battle_buff(
        95,
        BattleItemBuff(item_title="💎 Бриллиантовое Сердце", percent=18),
    )

    assert breakdown.base_score == 95
    assert breakdown.bonus_points == 5
    assert breakdown.final_score == 100


def test_score_breakdown_mentions_item_when_bonus_applies() -> None:
    breakdown = apply_collectible_battle_buff(
        70,
        BattleItemBuff(item_title="🔥 Пламя Безмятежности", percent=5),
    )

    assert format_score_breakdown("@user", breakdown) == (
        "@user: 70 + 4 за трофей «🔥 Пламя Безмятежности» (+5%) = 74/100"
    )


def test_score_breakdown_stays_plain_without_bonus() -> None:
    breakdown = apply_collectible_battle_buff(70, BattleItemBuff())

    assert format_score_breakdown("@user", breakdown) == "@user: 70/100"


def test_buffed_final_score_can_change_winner() -> None:
    user_without_buff = uuid4()
    user_with_buff = uuid4()
    score_breakdowns = {
        user_without_buff: apply_collectible_battle_buff(80, BattleItemBuff()),
        user_with_buff: apply_collectible_battle_buff(
            70,
            BattleItemBuff(item_title="💎 Бриллиантовое Сердце", percent=18),
        ),
    }

    assert (
        choose_battle_winner_id(
            [user_without_buff, user_with_buff],
            score_breakdowns,
            oracle_winner_id=user_without_buff,
        )
        == user_with_buff
    )
