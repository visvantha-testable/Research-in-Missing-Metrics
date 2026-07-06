"""Benchmark case: too-many-branches (R0912)."""


def too_many_branches(value):
    if value < 0:
        return "negative"
    if value == 0:
        return "zero"
    if value == 1:
        return "one"
    if value == 2:
        return "two"
    if value == 3:
        return "three"
    if value == 4:
        return "four"
    if value == 5:
        return "five"
    if value == 6:
        return "six"
    if value == 7:
        return "seven"
    if value == 8:
        return "eight"
    if value == 9:
        return "nine"
    if value == 10:
        return "ten"
    if value == 11:
        return "eleven"
    if value == 12:
        return "twelve"
    return "many"
