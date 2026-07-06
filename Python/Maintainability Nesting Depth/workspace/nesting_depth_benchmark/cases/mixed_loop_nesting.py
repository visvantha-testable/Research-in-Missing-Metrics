"""Nesting depth benchmark — mixed loop and branch nesting."""
from __future__ import annotations


def loop_nesting(items: list[int]) -> int:
    total = 0
    for item in items:
        if item > 0:
            for nested in items:
                if nested > 10:
                    for deep in items:
                        if deep > 20:
                            for deeper in items:
                                if deeper > 30:
                                    for deepest in items:
                                        if deepest > 40:
                                            total += deepest
    return total
