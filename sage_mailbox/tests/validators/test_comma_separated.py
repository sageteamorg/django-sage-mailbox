import pytest

from django.core.exceptions import ValidationError

from sage_mailbox.validators import CommaSeparatedEmailValidator


class TestCommaSeparatedEmailValidator:

    def setup_method(self):
        self.validator = CommaSeparatedEmailValidator()

    @pytest.mark.parametrize("emails", [
        "test@example.com",                          # Single valid email
        "test1@example.com, test2@example.com",      # Multiple valid emails
        "test1@example.com,   test2@example.com",    # Multiple valid emails with spaces
    ])
    def test_valid_emails(self, emails):
        # These should pass validation
        result = self.validator(emails)
        assert result is None

    @pytest.mark.parametrize("emails", [
        "invalid-email",                             # Single invalid email
        "valid@example.com, invalid-email",          # One valid, one invalid
        "invalid-email1, invalid-email2",            # Both invalid
        "test@",                                     # Missing domain
        "@example.com",                              # Missing local part
    ])
    def test_invalid_emails(self, emails):
        with pytest.raises(ValidationError):
            self.validator(emails)

    @pytest.mark.parametrize("emails", [
        "",                                          # Empty string
        "   test@example.com   ",                    # Valid email with leading/trailing spaces
        "valid@example.com,   ",                     # Valid email with trailing comma and space
    ])
    def test_edge_cases(self, emails):
        # These should pass validation
        result = self.validator(emails)
        assert result is None
