# Module-level single-line comments increase comment density.
# This file is used to validate Comment-to-Code Ratio extraction.
# Each section below documents intent for White Box metric testing.

"""Package-style module docstring counted as multi-line comment block.

Radon treats module docstrings as multi-line comments in raw metrics.
"""

# --- Helper section ---


def documented_add(left: int, right: int) -> int:
    """Add two integers and return the sum."""
    # Guard against unexpected types in benchmark-only code.
    result = left + right
    return result


def documented_multiply(left: int, right: int) -> int:
    """Multiply two integers."""
    # Inline comment before computation.
    product = left * right
    return product


# --- Processing section ---


def process_values(values: list[int]) -> int:
    """Aggregate a list of integers with inline documentation."""
    total = 0
    for value in values:
        # Accumulate each value into running total.
        total += value
    return total
