"""
Shared utility functions.
"""

# Minimum barbell increment: 1.25 kg plate on each side = 2.5 kg total.
# Valid weights from a 20 kg bar: 20, 22.5, 25, 27.5, 30, ...
_ROUND_INCREMENT = 2.5  # kg


def calculate_weight(one_rep_max: float, percentage: float) -> float:
    """
    Calculate working weight from a 1RM percentage, rounded to nearest 2.5 kg.

    Example: calculate_weight(125.0, 88.0) → 110.0
    """
    raw = one_rep_max * (percentage / 100)
    return round(raw / _ROUND_INCREMENT) * _ROUND_INCREMENT


def round_weight(weight_kg: float) -> float:
    """Round any weight value to the nearest 2.5 kg increment."""
    return round(weight_kg / _ROUND_INCREMENT) * _ROUND_INCREMENT


# Keep old name as alias so existing callers don't break
round_to_nearest_2_5 = round_weight
