import re

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_jsonform.models.fields import JSONField
from sage_imap.models.email import EmailMessage as EmailMessageDC

from sage_mailbox.models.mixins import TimestampMixin
from sage_mailbox.repository import EmailMessageManager
from sage_mailbox.validators import validate_comma_separated_email


class EmailMessage(TimestampMixin):
    HEADER_JSON_SCHEMA = {
        "type": "object",
        "readonly": True,
        "title": "Email Headers",
        "keys": {},
        "additionalProperties": {
            "type": "string",
            "readonly": True,
        },
    }
    uid = models.IntegerField(
        verbose_name=_("IMAP UID"),
        help_text=_("Unique identifier of the IMAP server."),
        db_comment="IMAP Server Unique Identifier (UID).",
        blank=True,
        null=True,
    )
    message_id = models.CharField(
        max_length=255,
        editable=False,
        null=True,
        blank=True,
        verbose_name=_("Message-ID Header"),
        help_text=_("Message ID from the email client's header."),
        db_comment="Message ID from the email client's header.",
    )
    subject = models.CharField(
        max_length=255,
        verbose_name=_("Subject"),
        help_text=_("Subject of the email."),
        db_comment="The subject of the email.",
    )
    from_address = models.EmailField(
        verbose_name=_("From Address"),
        help_text=_("Sender's email address."),
        db_comment="The sender's email address.",
    )
    to_address = models.TextField(
        verbose_name=_("To Address"),
        validators=[validate_comma_separated_email],
        help_text=_("Recipient email addresses (comma-separated)."),
        db_comment="List of recipient email addresses, separated by commas.",
    )
    cc_address = models.TextField(
        blank=True,
        verbose_name=_("CC Address"),
        validators=[validate_comma_separated_email],
        help_text=_("CC recipient email addresses (comma-separated)."),
        db_comment="List of CC recipient email addresses, separated by commas.",
    )
    bcc_address = models.TextField(
        blank=True,
        verbose_name=_("BCC Address"),
        validators=[validate_comma_separated_email],
        help_text=_("BCC recipient email addresses (comma-separated)."),
        db_comment="List of BCC recipient email addresses, separated by commas.",
    )
    date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date"),
        help_text=_("Date the email was sent (ISO format)."),
        db_comment="The date the email was sent, in ISO format.",
    )
    raw = models.BinaryField(
        blank=True,
        null=True,
        verbose_name=_("Raw Email Data"),
        help_text=_("Raw binary data of the email."),
        db_comment="The raw binary data of the email.",
    )
    plain_body = models.TextField(
        verbose_name=_("Plain Body"),
        help_text=_("Plain text body of the email."),
        db_comment="The plain text body content of the email.",
    )
    html_body = models.TextField(
        verbose_name=_("HTML Body"),
        help_text=_("HTML body of the email."),
        db_comment="The HTML body content of the email.",
    )
    flags = models.ManyToManyField(
        "Flag",
        blank=True,
        verbose_name=_("Flags"),
        help_text=_("Flags associated with the email."),
        db_comment="Flags associated with the email.",
    )
    headers = JSONField(
        schema=HEADER_JSON_SCHEMA,
        null=True,
        blank=True,
        verbose_name=_("Headers"),
        help_text=_("Email headers in JSON format."),
        db_comment="The email headers in JSON format.",
    )
    mailbox = models.ForeignKey(
        "Mailbox",
        related_name="emails",
        on_delete=models.CASCADE,
        verbose_name=_("Mailbox"),
        help_text=_("Mailbox to which this email belongs."),
        db_comment="The mailbox to which this email belongs.",
    )
    is_read = models.BooleanField(
        default=False,
        help_text=_("Indicates if the email has been read."),
        db_comment="Indicates whether the email has been read.",
        verbose_name=_("Is Read"),
    )
    is_flagged = models.BooleanField(
        default=False,
        help_text=_("Indicates if the email has been flagged."),
        db_comment="Indicates whether the email has been flagged.",
        verbose_name=_("Is Flagged"),
    )
    size = models.PositiveIntegerField(
        blank=True,
        null=True,
        default=0,
        verbose_name=_("Size"),
        help_text=_("Size of the email in bytes."),
        db_comment="Size of the email in bytes.",
    )

    objects = EmailMessageManager()

    class Meta:
        verbose_name = _("Inbox")
        verbose_name_plural = _("Inbox")
        default_manager_name = "objects"
        ordering = ["-date"]
        db_table = "sage_email_message"
        db_table_comment = "Model representing an email message."

        indexes = [
            models.Index(fields=["subject"], name="idx_email_subject"),
            models.Index(fields=["from_address"], name="idx_email_from_address"),
            models.Index(fields=["date"], name="idx_email_date"),
        ]

        permissions = [
            ("mark_read", _("Can mark email as read")),
            ("mark_unread", _("Can mark email as unread")),
            ("flag_email", _("Can flag email")),
            ("unflag_email", _("Can unflag email")),
            ("download_eml", _("Can download email data")),
        ]

    def save(self, *args, **kwargs):
        from sage_mailbox.models import Mailbox

        if not self.mailbox_id:
            sent_mailbox, _ = Mailbox.objects.get_or_create(name="Sent")
            self.mailbox = sent_mailbox
        super().save(*args, **kwargs)

    @classmethod
    def from_dataclass(cls, email_dc: EmailMessageDC):
        from sage_mailbox.models import Attachment, Flag

        """
        Convert a dataclass instance to a Django model instance.
        """
        email = cls(
            uid=email_dc.uid,
            message_id=email_dc.message_id,
            subject=email_dc.subject,
            from_address=email_dc.from_address,
            to_address=", ".join(email_dc.to_address),
            cc_address=", ".join(email_dc.cc_address),
            bcc_address=", ".join(email_dc.bcc_address),
            date=email_dc.date.isoformat() if email_dc.date else None,
            raw=email_dc.raw,
            plain_body=email_dc.plain_body,
            html_body=email_dc.html_body,
            size=email_dc.size,
        )
        email.save()
        # Process and clean up flags
        cleaned_flags = [re.sub(r"^\\+", "", flag.value) for flag in email_dc.flags]

        # Get existing flags from the database
        existing_flags = {
            flag.name: flag for flag in Flag.objects.filter(name__in=cleaned_flags)
        }

        # Find flags that need to be created
        new_flag_values = set(cleaned_flags) - set(existing_flags.keys())

        # Bulk create new flags
        new_flags = [Flag(name=value) for value in new_flag_values]
        Flag.objects.bulk_create(new_flags)

        # Retrieve all flags again (including newly created ones)
        all_flags = Flag.objects.filter(name__in=cleaned_flags)

        # Associate flags with the email
        email.flags.set(all_flags)
        # Handling attachments
        attachments = [
            Attachment(
                email=email,
                filename=attachment.filename,
                content_type=attachment.content_type,
                payload=attachment.payload,
                content_id=attachment.content_id,
                content_transfer_encoding=attachment.content_transfer_encoding,
            )
            for attachment in email_dc.attachments
        ]

        # Bulk create attachments
        Attachment.objects.bulk_create(attachments)
        return email

    def to_dataclass(self):
        """Convert a Django model instance to a dataclass instance."""
        from sage_imap.models.email import Attachment
        from sage_imap.models.email import EmailMessage as EmailMessageDC

        return EmailMessageDC(
            uid=self.uid,
            message_id=self.message_id,
            subject=self.subject,
            from_address=self.from_address,
            to_address=self.to_address,
            cc_address=self.cc_address,
            bcc_address=self.bcc_address,
            date=self.date.isoformat() if self.date else None,
            raw=self.raw,
            plain_body=self.plain_body,
            html_body=self.html_body,
            attachments=[
                Attachment(
                    id=attachment.id,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    payload=attachment.payload,
                    content_id=attachment.content_id,
                    content_transfer_encoding=attachment.content_transfer_encoding,
                )
                for attachment in self.attachments.all()
            ],
            flags=list(self.flags.all()),
            headers=self.headers,
            size=self.size,
        )

    @classmethod
    def sanitize_message_id(cls, message_id):
        pattern = r"<([^>]*)>"
        match = re.search(pattern, message_id)

        if match:
            sanitized_message_id = "<" + match.group(1) + ">"
        else:
            sanitized_message_id = None

        return sanitized_message_id

    def has_attachments(self):
        """Return True if the email has attachments, otherwise False."""
        return self.attachments.exists()

    def get_summary(self):
        """Return a summary of the email."""
        return {
            "subject": self.subject,
            "from": self.from_address,
            "to": self.to_address,
            "date": self.date,
            "has_attachments": self.has_attachments(),
        }

    def __repr__(self):
        return (
            f"<EmailMessage("
            f"subject={self.subject!r}, "
            f"from_address={self.from_address!r}, "
            f"date={self.date!r})>"
        )

    def __str__(self):
        return str(self.subject)


class Draft(EmailMessage):
    objects = EmailMessageManager()

    class Meta:
        proxy = True
        verbose_name = _("Draft")
        verbose_name_plural = _("Draft")


class Sent(EmailMessage):
    objects = EmailMessageManager()

    class Meta:
        proxy = True
        verbose_name = _("Sent")
        verbose_name_plural = _("Sent")


class Trash(EmailMessage):
    objects = EmailMessageManager()

    class Meta:
        proxy = True
        verbose_name = _("Trash")
        verbose_name_plural = _("Trash")


class Junk(EmailMessage):
    objects = EmailMessageManager()

    class Meta:
        proxy = True
        verbose_name = _("Junk")
        verbose_name_plural = _("Junk")


class Archive(EmailMessage):
    objects = EmailMessageManager()

    class Meta:
        proxy = True
        verbose_name = _("Archive")
        verbose_name_plural = _("Archive")
