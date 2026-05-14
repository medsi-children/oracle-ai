from __future__ import annotations


def psycoins(amount: int) -> str:
    value = abs(int(amount))
    if value % 100 in {11, 12, 13, 14}:
        word = "псикоинов"
    elif value % 10 == 1:
        word = "псикоин"
    elif value % 10 in {2, 3, 4}:
        word = "псикоина"
    else:
        word = "псикоинов"
    return f"{amount} {word}"
