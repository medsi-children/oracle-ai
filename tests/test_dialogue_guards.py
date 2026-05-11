from app.services.dialogue import (
    first_contact_reply_markup,
    group_only_reply,
    onboarding_required_reply,
    system_entry_required_reply,
)


def test_first_contact_markup_has_two_clear_choices() -> None:
    markup = first_contact_reply_markup()
    texts = [button.text for row in markup.inline_keyboard for button in row]

    assert texts == ["Начать проверку", "Мне нужно время"]


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
