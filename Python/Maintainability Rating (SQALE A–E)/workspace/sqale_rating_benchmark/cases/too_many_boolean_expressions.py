"""Benchmark case: too-many-boolean-expressions (R0916)."""


def too_many_boolean_expressions(a, b, c, d, e, f):
    if a and b and c and d and e and f:
        return True
    return False
