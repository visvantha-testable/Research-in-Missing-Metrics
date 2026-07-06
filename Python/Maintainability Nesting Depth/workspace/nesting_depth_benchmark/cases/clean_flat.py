"""Nesting depth benchmark — flat control flow (no nesting-depth violations)."""
from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b


def is_positive(value: int) -> bool:
    return value > 0


def classify(value: int) -> str:
    if value < 0:
        return "negative"
    if value == 0:
        return "zero"
    return "positive"
