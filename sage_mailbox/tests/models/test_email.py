import pytest
from django.utils import timezone
from model_bakery import baker
from sage_mailbox.models import EmailMessage


@pytest.mark.django_db
class TestEmailMessageModel:

    def test_sanitize_message_id(self):
        """Test the sanitize_message_id class method."""
        msg_id = "<test@example.com>"
        sanitized_id = EmailMessage.sanitize_message_id(msg_id)
        assert sanitized_id == "<test@example.com>"

        invalid_msg_id = "invalid_id"
        sanitized_invalid_id = EmailMessage.sanitize_message_id(invalid_msg_id)
        assert sanitized_invalid_id is None

    def test_to_dataclass(self):
        """Test conversion from EmailMessage to dataclass."""
        email = baker.make(EmailMessage, subject="Test subject")
        email_dc = email.to_dataclass()

        assert email_dc.subject == "Test subject"

    def test_has_attachments_method(self):
        """Test has_attachments method for EmailMessage."""
        email = baker.make(EmailMessage)
        baker.make('sage_mailbox.Attachment', email_message=email, _quantity=2)

        assert email.has_attachments() is True

    def test_get_summary(self):
        """Test get_summary method."""
        email = baker.make(
            EmailMessage,
            subject="Test",
            from_address="from@example.com",
            date=timezone.now()
        )
        summary = email.get_summary()

        assert summary["subject"] == "Test"
        assert summary["from"] == "from@example.com"
        assert "has_attachments" in summary
