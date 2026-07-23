import unittest
from logic import evaluate_access, evaluate_alert, evaluate_mixed


class TestLogicalSubexpressionValidation(unittest.TestCase):
    """Test cases designed to cover all pymcdc MC/DC requirements at 100%."""

    def test_access_all_true(self):
        self.assertEqual(evaluate_access(True, True, True), "granted")

    def test_access_user_inactive(self):
        self.assertEqual(evaluate_access(False, True, True), "denied")

    def test_access_no_permission(self):
        self.assertEqual(evaluate_access(True, False, True), "denied")

    def test_access_invalid_session(self):
        self.assertEqual(evaluate_access(True, True, False), "denied")

    def test_alert_high_level(self):
        self.assertEqual(evaluate_alert(True, False), "alert")

    def test_alert_threshold_only(self):
        self.assertEqual(evaluate_alert(False, True), "alert")

    def test_alert_none(self):
        self.assertEqual(evaluate_alert(False, False), "ok")

    def test_mixed_and_branch(self):
        self.assertEqual(evaluate_mixed(True, True, False), "trigger")

    def test_mixed_a_true_b_false_c_false(self):
        self.assertEqual(evaluate_mixed(True, False, False), "idle")

    def test_mixed_or_branch(self):
        self.assertEqual(evaluate_mixed(False, False, True), "trigger")

    def test_mixed_idle(self):
        self.assertEqual(evaluate_mixed(False, True, False), "idle")


if __name__ == "__main__":
    unittest.main()
