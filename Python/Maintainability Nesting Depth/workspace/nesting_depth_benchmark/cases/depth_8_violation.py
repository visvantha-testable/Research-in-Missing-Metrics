"""Nesting depth benchmark — 8 nested blocks (expected R1702 at depth 8/5)."""
from __future__ import annotations


def depth_eight(value: int) -> int:
    if value > 0:
        if value > 1:
            if value > 2:
                if value > 3:
                    if value > 4:
                        if value > 5:
                            if value > 6:
                                if value > 7:
                                    return value
    return 0
