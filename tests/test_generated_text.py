from app.services.llm import clean_generated_text


def test_clean_generated_text_removes_markdown_and_formats_sections() -> None:
    raw = (
        "**Что видно по вам** Вы обладаете высокой субъективностью. "
        "**Зоны роста**\n"
        "1.Конкретизировать действие после извинения.2.Внедрить практику."
    )

    cleaned = clean_generated_text(raw, split_sections=True)

    assert "*" not in cleaned
    assert "субъектив" not in cleaned.lower()
    assert "субъектностью" in cleaned
    assert "Что видно по вам\n\nВы обладаете" in cleaned
    assert "Зоны роста\n\n1. Конкретизировать" in cleaned
    assert "извинения.\n\n2. Внедрить" in cleaned
