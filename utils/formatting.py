"""utils/formatting.py — мелкие функции для красивых чисел"""

from math import floor


def num_thousand_sep(n: int | float, decimals: int = 0) -> str:
    fmt = f"{n:,.{decimals}f}" if decimals else f"{int(n):,}"
    return fmt.replace(",", " ")


def kg_str(value: float) -> str:
    return f"{value:.1f} кг"


def kcal_str(value: int) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{num_thousand_sep(value)} ккал"
