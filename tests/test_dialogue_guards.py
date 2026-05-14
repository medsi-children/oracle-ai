from types import SimpleNamespace

from app.services.dialogue import (
    first_contact_reply_markup,
    group_only_reply,
    handle_user_text,
    onboarding_required_reply,
    system_entry_required_reply,
)


def test_first_contact_markup_has_two_clear_choices() -> None:
    markup = first_contact_reply_markup()
    texts = [button.text for row in markup.inline_keyboard for button in row]

    assert texts == ["Я готов", "Мне нужно время"]


def test_onboarding_required_reply_points_to_start() -> None:
    assert "/start" in onboarding_required_reply()
    assert "7 вопросов" in onboarding_required_reply()


def test_system_entry_reply_mentions_mini_app_button() -> None:
    text = system_entry_required_reply()

    assert "синюю кнопку" in text
    assert "Войти в систему" in text


def test_group_only_reply_keeps_private_chat_useful() -> None:
    text = group_only_reply()

    assert "групповом чате" in text
    assert "/case" in text


async def test_onboarding_case_state_blocks_other_commands() -> None:
    user = SimpleNamespace(
        lifecycle_status="newbie",
        username="tester",
        status="object",
    )
    session = SimpleNamespace(state="onboarding:case:00000000-0000-0000-0000-000000000000:1")

    reply, mode, token_delta, markup = await handle_user_text(
        None,
        user=user,
        session=session,
        text="/case",
        chat_id=123,
        chat_type="private",
    )

    assert "проходите входную проверку" in reply
    assert mode == "onboarding_in_progress"
    assert token_delta == 0
    assert markup is None
