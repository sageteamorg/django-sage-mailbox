import logging

from dateutil import parser
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.timezone import make_aware
from sage_imap.helpers.enums import Flag, MessagePart
from sage_imap.helpers.search import IMAPSearchCriteria
from sage_imap.models.email import EmailMessage
from sage_imap.models.message import MessageSet
from sage_imap.services import IMAPClient, IMAPMailboxService

from sage_mailbox.models import Attachment as DjangoAttachment
from sage_mailbox.models import EmailMessage as DjangoEmailMessage
from sage_mailbox.models import Flag as DjangoFlag
from sage_mailbox.models import Mailbox as DjangoMailbox
from sage_mailbox.utils import sanitize_filename

logger = logging.getLogger(__name__)


# pylint: disable= C0103
class EmailSyncService:
    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password

    def fetch_and_save_emails(self, folder: str = "INBOX"):
        try:
            with IMAPClient(self.host, self.username, self.password) as client:
                with IMAPMailboxService(client) as mailbox:
                    mailbox.select(folder)

                    # Retrieve mailbox object or create a new one if it doesn't exist
                    mailbox_obj, _ = DjangoMailbox.objects.get_or_create(
                        name__contains=folder
                    )

                    # Get the latest email date from the database
                    latest_email = (
                        DjangoEmailMessage.objects.filter(mailbox=mailbox_obj)
                        .order_by("-created_at")
                        .first()
                    )

                    # If there are already synced emails, fetch from the latest date
                    if latest_email:
                        criteria = IMAPSearchCriteria.since(
                            latest_email.created_at.strftime("%d-%b-%Y")
                        )
                    else:
                        criteria = IMAPSearchCriteria.ALL

                    # Fetch emails based on the criteria
                    msg_ids = mailbox.search(criteria)
                    if msg_ids:
                        emails = mailbox.fetch(
                            MessageSet(msg_ids), MessagePart.BODY_PEEK
                        )
                        result = self.save_emails_to_db(emails, mailbox_obj)
                        return result

            return {"created_emails": 0, "created_attachments": 0}
        except Exception as exc:
            logger.error(f"Error fetching and saving emails: {exc}")
            return {"created_emails": 0, "created_attachments": 0}

    def save_emails_to_db(self, emails, mailbox):
        created_emails_count = 0
        created_attachments_count = 0

        for email in emails:
            created_email, created_attachments = self.create_or_update_email(
                email, mailbox
            )
            if created_email:
                created_emails_count += 1
            created_attachments_count += created_attachments

        return {
            "created_emails": created_emails_count,
            "created_attachments": created_attachments_count,
        }

    def create_or_update_email(self, email: EmailMessage, mailbox):
        # Determine if the email is read and flagged based on the flags
        is_read = Flag.SEEN in email.flags
        is_flagged = Flag.FLAGGED in email.flags

        # Create or update the EmailMessage
        try:
            # Parse the date string to a datetime object
            date_obj = parser.parse(email.date) if email.date else None

            # Make the datetime object timezone-aware
            aware_date = (
                make_aware(date_obj)
                if date_obj and date_obj.utcoffset() is None
                else date_obj
            )

        except (ValueError, TypeError, ValidationError):
            aware_date = None

        django_email, created = DjangoEmailMessage.objects.update_or_create(
            uid=email.uid,
            defaults={
                "message_id": email.message_id,
                "subject": email.subject,
                "from_address": email.from_address,
                "to_address": email.to_address,
                "cc_address": email.cc_address,
                "bcc_address": email.bcc_address,
                "date": aware_date,
                "raw": email.raw,
                "plain_body": email.plain_body,
                "html_body": email.html_body,
                "size": email.size,
                "is_read": is_read,
                "is_flagged": is_flagged,
                "headers": email.headers,
                "mailbox": mailbox,
            },
        )

        # Handle attachments
        created_attachments_count = self.handle_attachments(
            django_email, email.attachments
        )

        # Handle flags
        self.handle_flags(django_email, email.flags)

        return created, created_attachments_count

    def handle_attachments(self, django_email, attachments):
        created_attachments_count = 0

        for attachment in attachments:
            file_content = ContentFile(attachment.payload)
            sanitized_filename = sanitize_filename(attachment.filename)
            file_name = default_storage.save(
                f"attachments/{sanitized_filename}", file_content
            )

            DjangoAttachment.objects.update_or_create(
                email_message=django_email,
                filename=sanitized_filename,
                defaults={
                    "file": file_name,
                    "content_type": attachment.content_type,
                    "content_id": attachment.content_id,
                    "content_transfer_encoding": attachment.content_transfer_encoding,
                },
            )
            created_attachments_count += 1

        return created_attachments_count

    def handle_flags(self, django_email, flags):
        django_email.flags.clear()
        for flag in flags:
            flag_instance, created = DjangoFlag.objects.get_or_create(name=flag)
            django_email.flags.add(flag_instance)
