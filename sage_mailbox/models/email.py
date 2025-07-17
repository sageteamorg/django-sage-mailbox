"""
Email model for sage_mailbox.

This module contains the Email model for storing email messages.
The Email model is the core entity that represents individual email messages.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any

from django.db import models
from django.utils.translation import gettext_lazy as _

from sage_imap.helpers.enums import Flag
from sage_imap.models.email import EmailMessage as SageEmailMessage

from .mixins import TimestampMixin
from .mailbox import Mailbox
from .server import SMTPServer
from .template import EmailTemplate
from ..repository.manager import EmailManager


class Email(TimestampMixin):
    """
    Individual email message with full content and metadata.
    
    This model represents a single email message with all its content,
    metadata, and flags. It's the central model that connects to mailboxes,
    attachments, and handles both incoming and outgoing emails.
    
    The model supports:
    - Rich email content (HTML and plain text)
    - Email threading and replies
    - IMAP flags (read, flagged, deleted, etc.)
    - Attachment management
    - Email composition and sending
    - Trash management
    - Email templates
    
    Each email belongs to a specific mailbox and has a unique identifier (UID)
    assigned by the IMAP server.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for email"
    )
    
    mailbox = models.ForeignKey(
        Mailbox,
        on_delete=models.CASCADE,
        related_name="emails",
        verbose_name=_("Mailbox"),
        help_text=_("The folder where this email is stored"),
        db_comment="Reference to the mailbox containing this email"
    )
    
    uid = models.BigIntegerField(
        verbose_name=_("UID"),
        help_text=_("Unique number assigned by the email server to identify this message"),
        db_comment="Unique identifier from IMAP server (used for all operations)"
    )
    
    message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Message ID"),
        help_text=_("Unique identifier from the email header (used for threading and replies)"),
        db_comment="Message-ID header from email"
    )
    
    subject = models.TextField(
        blank=True,
        verbose_name=_("Subject"),
        help_text=_("The subject line of the email"),
        db_comment="Subject line of the email"
    )
    
    from_address = models.EmailField(
        blank=True,
        verbose_name=_("From address"),
        help_text=_("The email address of the person who sent this email"),
        db_comment="Sender's email address"
    )
    
    from_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("From name"),
        help_text=_("The display name of the person who sent this email"),
        db_comment="Sender's display name"
    )
    
    to_addresses = models.JSONField(
        default=list,
        verbose_name=_("To addresses"),
        help_text=_("List of email addresses this email was sent to"),
        db_comment="JSON array of recipient email addresses"
    )
    
    cc_addresses = models.JSONField(
        default=list,
        verbose_name=_("CC addresses"),
        help_text=_("List of email addresses that received a copy of this email"),
        db_comment="JSON array of CC recipient email addresses"
    )
    
    bcc_addresses = models.JSONField(
        default=list,
        verbose_name=_("BCC addresses"),
        help_text=_("List of email addresses that received a blind copy of this email"),
        db_comment="JSON array of BCC recipient email addresses"
    )
    
    date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date"),
        help_text=_("When this email was sent or received"),
        db_comment="Date and time when email was sent"
    )
    
    size = models.IntegerField(
        default=0,
        verbose_name=_("Size"),
        help_text=_("Size of the email in bytes (including attachments)"),
        db_comment="Size of the email in bytes"
    )
    
    plain_body = models.TextField(
        blank=True,
        verbose_name=_("Plain body"),
        help_text=_("The plain text version of the email content"),
        db_comment="Plain text body content"
    )
    
    html_body = models.TextField(
        blank=True,
        verbose_name=_("HTML body"),
        help_text=_("The rich HTML version of the email content"),
        db_comment="HTML body content"
    )
    
    headers = models.JSONField(
        default=dict,
        verbose_name=_("Headers"),
        help_text=_("Technical email headers (routing information, security data, etc.)"),
        db_comment="JSON object containing all email headers"
    )
    
    raw_content = models.BinaryField(
        null=True,
        blank=True,
        verbose_name=_("Raw content"),
        help_text=_("The complete raw email file (.eml format)"),
        db_comment="Raw email content in .eml format"
    )
    
    # Flags
    is_seen = models.BooleanField(
        default=False,
        verbose_name=_("Seen"),
        help_text=_("Has this email been read? Uncheck to mark as unread."),
        db_comment="Whether email has been read"
    )
    
    is_answered = models.BooleanField(
        default=False,
        verbose_name=_("Answered"),
        help_text=_("Has this email been replied to?"),
        db_comment="Whether email has been answered"
    )
    
    is_flagged = models.BooleanField(
        default=False,
        verbose_name=_("Flagged"),
        help_text=_("Is this email marked as important or needs attention?"),
        db_comment="Whether email is flagged as important"
    )
    
    is_deleted = models.BooleanField(
        default=False,
        verbose_name=_("Deleted"),
        help_text=_("Is this email marked for deletion?"),
        db_comment="Whether email is marked for deletion"
    )
    
    is_draft = models.BooleanField(
        default=False,
        verbose_name=_("Draft"),
        help_text=_("Is this email a draft that hasn't been sent yet?"),
        db_comment="Whether email is a draft"
    )
    
    is_recent = models.BooleanField(
        default=False,
        verbose_name=_("Recent"),
        help_text=_("Is this email newly arrived?"),
        db_comment="Whether email is recent"
    )
    
    # Trash management
    is_in_trash = models.BooleanField(
        default=False,
        verbose_name=_("In trash"),
        help_text=_("Is this email currently in the trash folder?"),
        db_comment="Whether email is in trash"
    )
    
    original_mailbox = models.ForeignKey(
        Mailbox,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trashed_emails",
        verbose_name=_("Original mailbox"),
        help_text=_("The folder this email was in before being moved to trash"),
        db_comment="Original mailbox before moving to trash"
    )
    
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Deleted at"),
        help_text=_("When this email was moved to trash"),
        db_comment="Timestamp when email was moved to trash"
    )
    
    # Email composition and sending fields
    smtp_server = models.ForeignKey(
        SMTPServer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_emails",
        verbose_name=_("SMTP Server"),
        help_text=_("The outgoing email server used to send this email"),
        db_comment="SMTP server used for sending this email"
    )
    
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emails",
        verbose_name=_("Template"),
        help_text=_("The email template used to create this email"),
        db_comment="Email template used for composition"
    )
    
    reply_to = models.EmailField(
        blank=True,
        verbose_name=_("Reply to"),
        help_text=_("The email address that should receive replies to this email"),
        db_comment="Reply-to email address"
    )
    
    priority = models.CharField(
        max_length=10,
        choices=[
            ('high', _('High')),
            ('normal', _('Normal')),
            ('low', _('Low')),
        ],
        default='normal',
        verbose_name=_("Priority"),
        help_text=_("The importance level of this email"),
        db_comment="Priority level of the email"
    )
    
    is_outgoing = models.BooleanField(
        default=False,
        verbose_name=_("Outgoing"),
        help_text=_("Was this email sent by us (outgoing) or received from someone else?"),
        db_comment="Whether this email is outgoing"
    )
    
    send_status = models.CharField(
        max_length=20,
        choices=[
            ('draft', _('Draft')),
            ('sending', _('Sending')),
            ('sent', _('Sent')),
            ('failed', _('Failed')),
        ],
        default='draft',
        verbose_name=_("Send status"),
        help_text=_("Current status of email sending process"),
        db_comment="Current sending status"
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Sent at"),
        help_text=_("When this email was successfully sent"),
        db_comment="Timestamp when email was sent"
    )
    
    send_attempts = models.IntegerField(
        default=0,
        verbose_name=_("Send attempts"),
        help_text=_("How many times we've tried to send this email"),
        db_comment="Number of send attempts"
    )
    
    send_error = models.TextField(
        blank=True,
        verbose_name=_("Send error"),
        help_text=_("Error message if email sending failed"),
        db_comment="Error message from failed send attempt"
    )
    
    in_reply_to = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("In reply to"),
        help_text=_("The Message-ID of the email this is replying to"),
        db_comment="Message-ID of email being replied to"
    )
    
    references = models.TextField(
        blank=True,
        verbose_name=_("References"),
        help_text=_("Chain of Message-IDs for email threading"),
        db_comment="References header for email threading"
    )
    
    objects: EmailManager = EmailManager()
    
    class Meta:
        db_table = "sage_email"
        verbose_name = _("Email")
        verbose_name_plural = _("Emails")
        unique_together = ["mailbox", "uid"]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["mailbox", "uid"]),
            models.Index(fields=["message_id"]),
            models.Index(fields=["from_address"]),
            models.Index(fields=["date"]),
            models.Index(fields=["is_seen"]),
            models.Index(fields=["is_flagged"]),
            models.Index(fields=["is_deleted"]),
            models.Index(fields=["is_in_trash"]),
        ]
    
    def __str__(self):
        return f"{self.subject} - {self.from_address}"
    
    def get_flags(self) -> List[str]:
        """Get list of flags for this email."""
        flags = []
        if self.is_seen:
            flags.append(Flag.SEEN)
        if self.is_answered:
            flags.append(Flag.ANSWERED)
        if self.is_flagged:
            flags.append(Flag.FLAGGED)
        if self.is_deleted:
            flags.append(Flag.DELETED)
        if self.is_draft:
            flags.append(Flag.DRAFT)
        if self.is_recent:
            flags.append(Flag.RECENT)
        return flags
    
    def set_flags(self, flags: List[str]):
        """Set flags for this email."""
        self.is_seen = Flag.SEEN in flags
        self.is_answered = Flag.ANSWERED in flags
        self.is_flagged = Flag.FLAGGED in flags
        self.is_deleted = Flag.DELETED in flags
        self.is_draft = Flag.DRAFT in flags
        self.is_recent = Flag.RECENT in flags
    
    @classmethod
    def from_sage_email(cls, sage_email: SageEmailMessage, mailbox: Mailbox, uid: int) -> "Email":
        """Create Django Email instance from sage_imap EmailMessage."""
        # Parse addresses
        to_addresses = [str(addr) for addr in sage_email.to_address]
        cc_addresses = [str(addr) for addr in sage_email.cc_address]
        bcc_addresses = [str(addr) for addr in sage_email.bcc_address]
        
        # Parse from address
        from_address = str(sage_email.from_address) if sage_email.from_address else ""
        from_name = ""
        if sage_email.from_address and hasattr(sage_email.from_address, 'display_name'):
            from_name = sage_email.from_address.display_name or ""
        
        # Parse date
        date = None
        if sage_email.date:
            try:
                date = datetime.fromisoformat(sage_email.date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        email = cls(
            mailbox=mailbox,
            uid=uid,
            message_id=sage_email.message_id,
            subject=sage_email.subject,
            from_address=from_address,
            from_name=from_name,
            to_addresses=to_addresses,
            cc_addresses=cc_addresses,
            bcc_addresses=bcc_addresses,
            date=date,
            size=sage_email.size,
            plain_body=sage_email.plain_body,
            html_body=sage_email.html_body,
            headers=sage_email.headers,
            raw_content=sage_email.raw,
        )
        
        # Set flags
        email.set_flags(sage_email.flags)
        
        return email
    
    def to_sage_email(self) -> SageEmailMessage:
        """Convert Django Email instance to sage_imap EmailMessage."""
        from sage_imap.helpers.typings import EmailAddress, EmailDate
        
        # Convert addresses
        to_addresses = [EmailAddress(addr) for addr in self.to_addresses]
        cc_addresses = [EmailAddress(addr) for addr in self.cc_addresses]
        bcc_addresses = [EmailAddress(addr) for addr in self.bcc_addresses]
        
        from_address = EmailAddress(self.from_address) if self.from_address else None
        
        # Convert date
        date = EmailDate(self.date.isoformat()) if self.date else None
        
        return SageEmailMessage(
            message_id=self.message_id,
            subject=self.subject,
            from_address=from_address,
            to_address=to_addresses,
            cc_address=cc_addresses,
            bcc_address=bcc_addresses,
            date=date,
            raw=self.raw_content,
            plain_body=self.plain_body,
            html_body=self.html_body,
            headers=self.headers,
            flags=self.get_flags(),
            size=self.size,
        ) 