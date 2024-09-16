# import pytest
# from unittest.mock import patch, MagicMock
# from dateutil import parser
# from sage_mailbox.repository.service import EmailSyncService


# from sage_mailbox.models import EmailMessage as DjangoEmailMessage
# from sage_mailbox.models import Mailbox as DjangoMailbox
# from sage_mailbox.models import Attachment as DjangoAttachment
# from sage_mailbox.models import Flag as DjangoFlag


# from sage_imap.services import IMAPClient, IMAPMailboxService
# from sage_imap.helpers.enums import Flag, MessagePart
# from sage_imap.helpers.search import IMAPSearchCriteria
# from sage_imap.models.message import MessageSet
# from sage_imap.models.email import EmailMessage

# # Sample data for tests
# SAMPLE_EMAIL = EmailMessage(
#     uid="123",
#     message_id="msg-123",
#     subject="Test Subject",
#     from_address="from@example.com",
#     to_address=["to@example.com"],
#     cc_address=[],
#     bcc_address=[],
#     date="01-Jan-2021",
#     raw=b"Raw message content",  # Ensure raw is bytes
#     plain_body="Plain body content",
#     html_body="<html>HTML body content</html>",
#     size=1024,
#     flags=[Flag.SEEN, Flag.FLAGGED],
#     headers={"Message-ID": "<msg-123>", "subject": "Test Subject"},
#     attachments=[]
# )


# @pytest.fixture
# def email_sync_service():
#     """Fixture to instantiate the EmailSyncService."""
#     return EmailSyncService(host="imap.example.com", username="user", password="password")


# @pytest.fixture
# def mocked_mailbox():
#     """Fixture to mock IMAPMailboxService."""
#     with patch("sage_imap.services.IMAPMailboxService") as mock_mailbox:
#         yield mock_mailbox


# @pytest.fixture
# def mocked_client():
#     """Fixture to mock IMAPClient."""
#     with patch("sage_imap.services.IMAPClient") as mock_client:
#         yield mock_client


# @pytest.fixture
# def mocked_django_models():
#     """Fixture to mock Django model interactions."""
#     with patch("sage_mailbox.models.EmailMessage.objects.update_or_create") as mock_update_or_create, \
#          patch("sage_mailbox.models.Mailbox.objects.get_or_create") as mock_get_or_create, \
#          patch("sage_mailbox.models.Attachment.objects.update_or_create") as mock_attachment_create, \
#          patch("sage_mailbox.models.Flag.objects.get_or_create") as mock_flag_create:
#         mock_update_or_create.return_value = (MagicMock(), True)  # Mocking the return values
#         mock_get_or_create.return_value = (MagicMock(), True)  # Mock Mailbox get_or_create
#         mock_attachment_create.return_value = (MagicMock(), True)  # Mock Attachment creation
#         mock_flag_create.return_value = (MagicMock(), True)  # Mock Flag creation
#         yield mock_update_or_create, mock_get_or_create, mock_attachment_create, mock_flag_create


# class TestEmailSyncService:
#     def test_service_initialization(self, email_sync_service):
#         """Test the initialization of EmailSyncService."""
#         assert email_sync_service.host == "imap.example.com"
#         assert email_sync_service.username == "user"
#         assert email_sync_service.password == "password"

#     def test_fetch_emails_from_default_inbox(self, email_sync_service, mocked_client, mocked_mailbox, mocked_django_models):
#         """Test fetching emails from the default folder 'INBOX'."""
#         mock_mailbox_instance = mocked_mailbox.return_value
#         mock_mailbox_instance.search.return_value = [1, 2, 3]  # Fake message IDs
#         mock_mailbox_instance.fetch.return_value = [SAMPLE_EMAIL]

#         # Mock Django mailbox retrieval/creation
#         mock_django_email_message, mock_mailbox_obj = mocked_django_models[1], mocked_django_models[0]
#         mock_django_email_message.filter.return_value.order_by.return_value.first.return_value = None

#         result = email_sync_service.fetch_and_save_emails()

#         assert result == {"created_emails": 1, "created_attachments": 0}
#         mock_mailbox_instance.search.assert_called_once_with(IMAPSearchCriteria.ALL)
#         mock_mailbox_instance.fetch.assert_called_once()

#     def test_fetch_emails_with_latest_date(self, email_sync_service, mocked_client, mocked_mailbox, mocked_django_models):
#         """Test fetching emails when there's already synced emails in the database."""
#         mock_mailbox_instance = mocked_mailbox.return_value
#         mock_mailbox_instance.search.return_value = [1, 2, 3]  # Fake message IDs
#         mock_mailbox_instance.fetch.return_value = [SAMPLE_EMAIL]

#         # Mock latest email creation date
#         latest_email = MagicMock()
#         latest_email.created_at = parser.parse("2021-01-01")
#         mock_django_email_message, _ = mocked_django_models[1], mocked_django_models[0]
#         mock_django_email_message.filter.return_value.order_by.return_value.first.return_value = latest_email

#         result = email_sync_service.fetch_and_save_emails()

#         assert result == {"created_emails": 1, "created_attachments": 0}
#         mock_mailbox_instance.search.assert_called_once()
#         mock_mailbox_instance.fetch.assert_called_once()

#     def test_handle_invalid_email_date(self, email_sync_service, mocked_django_models):
#         """Test saving email when email.date is invalid."""
#         invalid_email = SAMPLE_EMAIL
#         invalid_email.date = "invalid-date"

#         mock_django_email_message, _ = mocked_django_models[1], mocked_django_models[0]
#         email_sync_service.create_or_update_email(invalid_email, MagicMock())

#         mock_django_email_message.update_or_create.assert_called_once()

#     def test_save_email_with_attachments(self, email_sync_service, mocked_django_models):
#         """Test saving email with attachments."""
#         attachment = MagicMock(filename="file.txt", payload=b"file_content", content_type="text/plain")
#         email_with_attachments = SAMPLE_EMAIL
#         email_with_attachments.attachments = [attachment]

#         mock_django_email_message, _ = mocked_django_models[1], mocked_django_models[0]
#         result = email_sync_service.create_or_update_email(email_with_attachments, MagicMock())

#         mock_django_email_message.update_or_create.assert_called_once()
#         assert result == (True, 1)  # One email and one attachment created

#     def test_error_handling_in_fetch_and_save_emails(self, email_sync_service, mocked_mailbox):
#         """Test error handling during email fetching."""
#         mock_mailbox_instance = mocked_mailbox.return_value
#         mock_mailbox_instance.search.side_effect = Exception("IMAP error")

#         result = email_sync_service.fetch_and_save_emails()
#         assert result == {"created_emails": 0, "created_attachments": 0}

#     def test_handle_flags_for_email(self, email_sync_service, mocked_django_models):
#         """Test handling flags for an email."""
#         mock_django_flag, _ = mocked_django_models[3], mocked_django_models[0]

#         email_sync_service.handle_flags(MagicMock(), [Flag.SEEN, Flag.FLAGGED])

#         assert mock_django_flag.call_count == 2  # Two flags should be created or retrieved

#     def test_handle_no_attachments(self, email_sync_service, mocked_django_models):
#         """Test saving an email with no attachments."""
#         mock_django_email_message, _ = mocked_django_models[1], mocked_django_models[0]

#         result = email_sync_service.create_or_update_email(SAMPLE_EMAIL, MagicMock())

#         mock_django_email_message.update_or_create.assert_called_once()
#         assert result == (True, 0)  # One email and zero attachments created
