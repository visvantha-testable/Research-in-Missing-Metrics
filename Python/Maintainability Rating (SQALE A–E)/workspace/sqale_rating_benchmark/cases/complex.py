"""High complexity module with lower maintainability."""

def complex_router(value):
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
    return "other"

def nested_decisions(a, b, c, d):
    result = 0
    if a:
        if b:
            if c:
                if d:
                    result += 1
                else:
                    result += 2
            else:
                result += 3
        else:
            result += 4
    else:
        result += 5
    return result
