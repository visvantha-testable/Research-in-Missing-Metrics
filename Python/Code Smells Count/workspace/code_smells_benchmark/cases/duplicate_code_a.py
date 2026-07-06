"""Benchmark case: duplicate-code partner A (R0801)."""


def duplicate_logic_alpha(x, y, z):
    result = 0
    if x > 0:
        result += x
    if y > 0:
        result += y
    if z > 0:
        result += z
    for item in [x, y, z]:
        if item % 2 == 0:
            result += item
    return result
