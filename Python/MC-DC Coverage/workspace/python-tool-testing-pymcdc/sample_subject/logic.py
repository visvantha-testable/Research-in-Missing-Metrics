"""Training subject for Logical Sub-expression Validation (MC/DC)."""


def evaluate_access(user_active: bool, has_permission: bool, session_valid: bool) -> str:
    """Compound AND decision — each sub-expression must be True and False."""
    if user_active and has_permission and session_valid:
        return "granted"
    return "denied"


def evaluate_alert(level_high: bool, threshold_exceeded: bool) -> str:
    """Compound OR decision — short-circuit aware sub-expression validation."""
    if level_high or threshold_exceeded:
        return "alert"
    return "ok"


def evaluate_mixed(flag_a: bool, flag_b: bool, flag_c: bool) -> str:
    """Mixed AND/OR — additional decision points for MC/DC training."""
    if (flag_a and flag_b) or flag_c:
        return "trigger"
    return "idle"
