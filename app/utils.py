"""
Shared utility functions.
"""

_ROUND_INCREMENT = 1.25  # kg — change here to adjust rounding globally


def calculate_weight(one_rep_max: float, percentage: float) -> float:
    """
    Calculate working weight from a 1RM percentage, rounded to nearest 1.25 kg.

    Example: calculate_weight(125.0, 88.0) → 110.0
    """
    raw = one_rep_max * (percentage / 100)
    return round(raw / _ROUND_INCREMENT) * _ROUND_INCREMENT


def round_weight(weight_kg: float) -> float:
    """Round any weight value to the nearest 1.25 kg increment."""
    return round(weight_kg / _ROUND_INCREMENT) * _ROUND_INCREMENT


# Keep old name as alias so existing callers don't break
round_to_nearest_2_5 = round_weight
