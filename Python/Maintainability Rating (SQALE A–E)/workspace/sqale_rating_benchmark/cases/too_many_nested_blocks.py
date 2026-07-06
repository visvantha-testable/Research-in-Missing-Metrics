"""Benchmark case: too-many-nested-blocks (R1702)."""


def too_many_nested_blocks(value):
    if value > 0:
        if value > 1:
            if value > 2:
                if value > 3:
                    if value > 4:
                        if value > 5:
                            return value
    return 0
