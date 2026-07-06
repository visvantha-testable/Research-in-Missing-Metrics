"""Moderate complexity module."""

def classify(value):
    if value < 10:
        return "low"
    if value < 20:
        return "medium"
    if value < 30:
        return "high"
    return "very_high"

def summarize(values):
    total = 0
    for item in values:
        total += item
    return total
