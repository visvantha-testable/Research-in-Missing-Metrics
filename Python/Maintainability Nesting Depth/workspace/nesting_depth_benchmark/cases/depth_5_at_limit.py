"""Nesting depth benchmark — exactly 5 nested blocks (at Pylint default limit)."""
from __future__ import annotations


def at_limit(value: int) -> int:
    if value > 0:
        if value > 1:
            if value > 2:
                if value > 3:
                    if value > 4:
                        return value
    return 0
