"""Benchmark case: too-many-return-statements (R0911)."""


def too_many_returns(value):
    if value < 0:
        return -1
    if value == 0:
        return 0
    if value == 1:
        return 1
    if value == 2:
        return 2
    if value == 3:
        return 3
    if value == 4:
        return 4
    if value == 5:
        return 5
    if value == 6:
        return 6
    return value
