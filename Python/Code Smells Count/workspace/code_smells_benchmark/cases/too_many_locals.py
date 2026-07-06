"""Benchmark case: too-many-locals (R0914)."""


def too_many_locals(seed):
    v01 = seed + 1
    v02 = seed + 2
    v03 = seed + 3
    v04 = seed + 4
    v05 = seed + 5
    v06 = seed + 6
    v07 = seed + 7
    v08 = seed + 8
    v09 = seed + 9
    v10 = seed + 10
    v11 = seed + 11
    v12 = seed + 12
    v13 = seed + 13
    v14 = seed + 14
    v15 = seed + 15
    v16 = seed + 16
    return v01 + v02 + v03 + v04 + v05 + v06 + v07 + v08 + v09 + v10 + v11 + v12 + v13 + v14 + v15 + v16
