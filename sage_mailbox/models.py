import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from sage_imap.helpers.enums import Flag, DefaultMailboxes
from sage_imap.models.email import EmailMessage as SageEmailMessage
from sage_imap.models.email import Attachment as SageAttachment

from .repository.manager import EmailManager, MailboxManager


class TimestampMixin(models.Model):
    """Base mixin for timestamp fields."""
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("The date and time when this record was created"),
        db_comment="Timestamp when record was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at"),
        help_text=_("The date and time when this record was last updated"),
        db_comment="Timestamp when record was last updated"
    )
    
    class Meta:
        abstract = True


class IMAPServer(TimestampMixin):
    """
    Model for storing IMAP server configurations.
    
    Represents connection details for different IMAP servers.
    Supports multiple servers for different users or organizations.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for IMAP server configuration"
    )
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Server name"),
        help_text=_("A friendly name for this IMAP server (e.g., 'Company Gmail')"),
        db_comment="Human-readable name for the server"
    )
    
    host = models.CharField(
        max_length=255,
        verbose_name=_("IMAP host"),
        help_text=_("The hostname or IP address of the IMAP server"),
        db_comment="IMAP server hostname or IP address"
    )
    
    port = models.PositiveIntegerField(
        default=993,
        verbose_name=_("Port"),
        help_text=_("The port number for IMAP connection (usually 993 for SSL)"),
        db_comment="Port number for IMAP connection"
    )
    
    username = models.CharField(
        max_length=255,
        verbose_name=_("Username"),
        help_text=_("The username for IMAP authentication"),
        db_comment="Username for IMAP server authentication"
    )
    
    password = models.CharField(
        max_length=255,
        verbose_name=_("Password"),
        help_text=_("The password for IMAP authentication (encrypted)"),
        db_comment="Encrypted password for IMAP server authentication"
    )
    
    use_ssl = models.BooleanField(
        default=True,
        verbose_name=_("Use SSL"),
        help_text=_("Whether to use SSL encryption for the connection"),
        db_comment="Whether SSL encryption is enabled"
    )
    
    timeout = models.FloatField(
        default=30.0,
        verbose_name=_("Timeout"),
        help_text=_("Connection timeout in seconds"),
        db_comment="Connection timeout in seconds"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Whether this server configuration is active"),
        db_comment="Whether server configuration is active"
    )
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="imap_servers",
        verbose_name=_("Owner"),
        help_text=_("The user who owns this IMAP server configuration"),
        db_comment="User who owns this server configuration"
    )
    
    class Meta:
        db_table = "sage_imap_server"
        verbose_name = _("IMAP Server")
        verbose_name_plural = _("IMAP Servers")
        ordering = ["name"]
    
    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"
    
    def clean(self):
        if self.port <= 0 or self.port > 65535:
            raise ValidationError(_("Port must be between 1 and 65535"))
        
        if self.timeout <= 0:
            raise ValidationError(_("Timeout must be greater than 0"))
    
    def save(self, *args, **kwargs):
        """Override save to encrypt password."""
        from .security.encryption import password_encryption
        
        # Only encrypt if password was changed and is not already encrypted
        if self.password and not self._is_password_encrypted():
            self.password = password_encryption.encrypt_password(self.password)
        
        super().save(*args, **kwargs)
    
    def _is_password_encrypted(self):
        """Check if password is already encrypted."""
        if not self.password:
            return False
            
        try:
            # Check if it's encrypted by trying to decrypt it
            from .security.encryption import password_encryption
            password_encryption.decrypt_password(self.password)
            return True
        except Exception:
            # If decryption fails, it's not encrypted
            return False
    
    def get_decrypted_password(self):
        """Get the decrypted password for use in connections."""
        from .security.encryption import password_encryption
        
        if not self.password:
            return ""
        
        # If password doesn't look encrypted, return as-is (for migration purposes)
        if not self._is_password_encrypted():
            return self.password
        
        try:
            return password_encryption.decrypt_password(self.password)
        except Exception as e:
            # If decryption fails, assume it's plain text (for migration)
            return self.password


class SMTPServer(TimestampMixin):
    """
    Model for storing SMTP server configurations.
    
    Represents connection details for different SMTP servers for sending emails.
    Supports multiple servers for different users or organizations.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for SMTP server configuration"
    )
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Server name"),
        help_text=_("A friendly name for this SMTP server (e.g., 'Company Gmail SMTP')"),
        db_comment="Human-readable name for the server"
    )
    
    host = models.CharField(
        max_length=255,
        verbose_name=_("SMTP host"),
        help_text=_("The hostname or IP address of the SMTP server"),
        db_comment="SMTP server hostname or IP address"
    )
    
    port = models.PositiveIntegerField(
        default=587,
        verbose_name=_("Port"),
        help_text=_("The port number for SMTP connection (usually 587 for TLS, 465 for SSL)"),
        db_comment="Port number for SMTP connection"
    )
    
    username = models.CharField(
        max_length=255,
        verbose_name=_("Username"),
        help_text=_("The username for SMTP authentication"),
        db_comment="Username for SMTP server authentication"
    )
    
    password = models.CharField(
        max_length=255,
        verbose_name=_("Password"),
        help_text=_("The password for SMTP authentication (encrypted)"),
        db_comment="Encrypted password for SMTP server authentication"
    )
    
    use_tls = models.BooleanField(
        default=True,
        verbose_name=_("Use TLS"),
        help_text=_("Whether to use TLS encryption for the connection"),
        db_comment="Whether TLS encryption is enabled"
    )
    
    use_ssl = models.BooleanField(
        default=False,
        verbose_name=_("Use SSL"),
        help_text=_("Whether to use SSL encryption for the connection"),
        db_comment="Whether SSL encryption is enabled"
    )
    
    timeout = models.FloatField(
        default=30.0,
        verbose_name=_("Timeout"),
        help_text=_("Connection timeout in seconds"),
        db_comment="Connection timeout in seconds"
    )
    
    from_email = models.EmailField(
        verbose_name=_("From email"),
        help_text=_("The default email address to use as sender"),
        db_comment="Default sender email address"
    )
    
    from_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("From name"),
        help_text=_("The default name to use as sender"),
        db_comment="Default sender name"
    )
    
    signature = models.TextField(
        blank=True,
        verbose_name=_("Email signature"),
        help_text=_("Default email signature to append to emails"),
        db_comment="Default email signature"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Whether this server configuration is active"),
        db_comment="Whether server configuration is active"
    )
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="smtp_servers",
        verbose_name=_("Owner"),
        help_text=_("The user who owns this SMTP server configuration"),
        db_comment="User who owns this server configuration"
    )
    
    class Meta:
        db_table = "sage_smtp_server"
        verbose_name = _("SMTP Server")
        verbose_name_plural = _("SMTP Servers")
        ordering = ["name"]
    
    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"
    
    def clean(self):
        if self.port <= 0 or self.port > 65535:
            raise ValidationError(_("Port must be between 1 and 65535"))
        
        if self.timeout <= 0:
            raise ValidationError(_("Timeout must be greater than 0"))
        
        if self.use_tls and self.use_ssl:
            raise ValidationError(_("Cannot use both TLS and SSL encryption"))
    
    def save(self, *args, **kwargs):
        """Override save to encrypt password."""
        from .security.encryption import password_encryption
        
        # Only encrypt if password was changed and is not already encrypted
        if self.password and not self._is_password_encrypted():
            self.password = password_encryption.encrypt_password(self.password)
        
        super().save(*args, **kwargs)
    
    def _is_password_encrypted(self):
        """Check if password is already encrypted."""
        if not self.password:
            return False
            
        try:
            # Check if it's encrypted by trying to decrypt it
            from .security.encryption import password_encryption
            password_encryption.decrypt_password(self.password)
            return True
        except Exception:
            # If decryption fails, it's not encrypted
            return False
    
    def get_decrypted_password(self):
        """Get the decrypted password for use in connections."""
        from .security.encryption import password_encryption
        
        if not self.password:
            return ""
        
        # If password doesn't look encrypted, return as-is (for migration purposes)
        if not self._is_password_encrypted():
            return self.password
        
        try:
            return password_encryption.decrypt_password(self.password)
        except Exception as e:
            # If decryption fails, assume it's plain text (for migration)
            return self.password


class EmailTemplate(TimestampMixin):
    """
    Model for storing email templates.
    
    Allows users to create reusable email templates for common messages.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for email template"
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name=_("Template name"),
        help_text=_("A descriptive name for this email template"),
        db_comment="Name of the email template"
    )
    
    subject = models.CharField(
        max_length=255,
        verbose_name=_("Subject"),
        help_text=_("The subject line for emails created from this template"),
        db_comment="Email subject template"
    )
    
    body_html = models.TextField(
        blank=True,
        verbose_name=_("HTML body"),
        help_text=_("The HTML content of the email template"),
        db_comment="HTML body of the email template"
    )
    
    body_plain = models.TextField(
        blank=True,
        verbose_name=_("Plain text body"),
        help_text=_("The plain text content of the email template"),
        db_comment="Plain text body of the email template"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_("Whether this template is active and available for use"),
        db_comment="Whether template is active"
    )
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_templates",
        verbose_name=_("Owner"),
        help_text=_("The user who owns this email template"),
        db_comment="User who owns this template"
    )
    
    class Meta:
        db_table = "sage_email_template"
        verbose_name = _("Email Template")
        verbose_name_plural = _("Email Templates")
        ordering = ["name"]
        unique_together = ["name", "owner"]
    
    def __str__(self):
        return f"{self.name} ({self.owner.username})"


class Mailbox(TimestampMixin):
    """
    Model for storing IMAP mailbox/folder information.
    
    Represents individual mailboxes (folders) within an IMAP server.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for mailbox"
    )
    
    server = models.ForeignKey(
        IMAPServer,
        on_delete=models.CASCADE,
        related_name="mailboxes",
        verbose_name=_("IMAP Server"),
        help_text=_("The IMAP server this mailbox belongs to"),
        db_comment="Reference to the IMAP server"
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name=_("Mailbox name"),
        help_text=_("The name of the mailbox/folder on the server"),
        db_comment="Name of the mailbox on the IMAP server"
    )
    
    display_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Display name"),
        help_text=_("A friendly display name for this mailbox"),
        db_comment="Human-readable display name"
    )
    
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Default mailbox"),
        help_text=_("Whether this is a default system mailbox (INBOX, Sent, etc.)"),
        db_comment="Whether this is a default system mailbox"
    )
    
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Parent mailbox"),
        help_text=_("The parent mailbox if this is a sub-folder"),
        db_comment="Parent mailbox for nested folder structure"
    )
    
    delimiter = models.CharField(
        max_length=5,
        default="/",
        verbose_name=_("Delimiter"),
        help_text=_("The delimiter used for folder hierarchy"),
        db_comment="Delimiter character for folder hierarchy"
    )
    
    uidvalidity = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("UID validity"),
        help_text=_("The UIDVALIDITY value from the server"),
        db_comment="UIDVALIDITY value from IMAP server"
    )
    
    uidnext = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("UID next"),
        help_text=_("The UIDNEXT value from the server"),
        db_comment="UIDNEXT value from IMAP server"
    )
    
    message_count = models.IntegerField(
        default=0,
        verbose_name=_("Message count"),
        help_text=_("Total number of messages in this mailbox"),
        db_comment="Total number of messages in mailbox"
    )
    
    unseen_count = models.IntegerField(
        default=0,
        verbose_name=_("Unseen count"),
        help_text=_("Number of unseen messages in this mailbox"),
        db_comment="Number of unseen messages in mailbox"
    )
    
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last sync"),
        help_text=_("The last time this mailbox was synchronized"),
        db_comment="Timestamp of last synchronization"
    )
    
    # Custom manager
    objects = MailboxManager()
    
    class Meta:
        db_table = "sage_mailbox"
        verbose_name = _("Mailbox")
        verbose_name_plural = _("Mailboxes")
        unique_together = ["server", "name"]
        ordering = ["server", "name"]
    
    def __str__(self):
        return f"{self.server.name}/{self.name}"
    
    @property
    def full_name(self):
        """Get the full hierarchical name of the mailbox."""
        if self.parent:
            return f"{self.parent.full_name}{self.delimiter}{self.name}"
        return self.name
    
    def get_display_name(self):
        """Get the display name or fallback to name."""
        return self.display_name or self.name


class Email(TimestampMixin):
    """
    Model for storing email messages.
    
    Represents individual email messages with all their metadata.
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
        help_text=_("The mailbox this email belongs to"),
        db_comment="Reference to the mailbox containing this email"
    )
    
    uid = models.BigIntegerField(
        verbose_name=_("UID"),
        help_text=_("The unique identifier assigned by the IMAP server"),
        db_comment="Unique identifier from IMAP server (used for all operations)"
    )
    
    message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Message ID"),
        help_text=_("The Message-ID header from the email"),
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
        help_text=_("The sender's email address"),
        db_comment="Sender's email address"
    )
    
    from_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("From name"),
        help_text=_("The sender's display name"),
        db_comment="Sender's display name"
    )
    
    to_addresses = models.JSONField(
        default=list,
        verbose_name=_("To addresses"),
        help_text=_("List of recipient email addresses"),
        db_comment="JSON array of recipient email addresses"
    )
    
    cc_addresses = models.JSONField(
        default=list,
        verbose_name=_("CC addresses"),
        help_text=_("List of CC recipient email addresses"),
        db_comment="JSON array of CC recipient email addresses"
    )
    
    bcc_addresses = models.JSONField(
        default=list,
        verbose_name=_("BCC addresses"),
        help_text=_("List of BCC recipient email addresses"),
        db_comment="JSON array of BCC recipient email addresses"
    )
    
    date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date"),
        help_text=_("The date and time when the email was sent"),
        db_comment="Date and time when email was sent"
    )
    
    size = models.IntegerField(
        default=0,
        verbose_name=_("Size"),
        help_text=_("The size of the email in bytes"),
        db_comment="Size of the email in bytes"
    )
    
    plain_body = models.TextField(
        blank=True,
        verbose_name=_("Plain body"),
        help_text=_("The plain text body of the email"),
        db_comment="Plain text body content"
    )
    
    html_body = models.TextField(
        blank=True,
        verbose_name=_("HTML body"),
        help_text=_("The HTML body of the email"),
        db_comment="HTML body content"
    )
    
    headers = models.JSONField(
        default=dict,
        verbose_name=_("Headers"),
        help_text=_("All email headers as key-value pairs"),
        db_comment="JSON object containing all email headers"
    )
    
    raw_content = models.BinaryField(
        null=True,
        blank=True,
        verbose_name=_("Raw content"),
        help_text=_("The raw email content (.eml format)"),
        db_comment="Raw email content in .eml format"
    )
    
    # Flags
    is_seen = models.BooleanField(
        default=False,
        verbose_name=_("Seen"),
        help_text=_("Whether the email has been read"),
        db_comment="Whether email has been read"
    )
    
    is_answered = models.BooleanField(
        default=False,
        verbose_name=_("Answered"),
        help_text=_("Whether the email has been answered"),
        db_comment="Whether email has been answered"
    )
    
    is_flagged = models.BooleanField(
        default=False,
        verbose_name=_("Flagged"),
        help_text=_("Whether the email is flagged as important"),
        db_comment="Whether email is flagged as important"
    )
    
    is_deleted = models.BooleanField(
        default=False,
        verbose_name=_("Deleted"),
        help_text=_("Whether the email is marked for deletion"),
        db_comment="Whether email is marked for deletion"
    )
    
    is_draft = models.BooleanField(
        default=False,
        verbose_name=_("Draft"),
        help_text=_("Whether the email is a draft"),
        db_comment="Whether email is a draft"
    )
    
    is_recent = models.BooleanField(
        default=False,
        verbose_name=_("Recent"),
        help_text=_("Whether the email is recent"),
        db_comment="Whether email is recent"
    )
    
    # Trash management
    is_in_trash = models.BooleanField(
        default=False,
        verbose_name=_("In trash"),
        help_text=_("Whether the email is in trash"),
        db_comment="Whether email is in trash"
    )
    
    original_mailbox = models.ForeignKey(
        Mailbox,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trashed_emails",
        verbose_name=_("Original mailbox"),
        help_text=_("The original mailbox before moving to trash"),
        db_comment="Original mailbox before moving to trash"
    )
    
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Deleted at"),
        help_text=_("When the email was moved to trash"),
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
        help_text=_("The SMTP server used to send this email"),
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
        help_text=_("The reply-to email address"),
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
        help_text=_("The priority level of the email"),
        db_comment="Priority level of the email"
    )
    
    is_outgoing = models.BooleanField(
        default=False,
        verbose_name=_("Outgoing"),
        help_text=_("Whether this email is outgoing (sent by us)"),
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
        help_text=_("The current sending status of the email"),
        db_comment="Current sending status"
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Sent at"),
        help_text=_("When the email was successfully sent"),
        db_comment="Timestamp when email was sent"
    )
    
    send_attempts = models.IntegerField(
        default=0,
        verbose_name=_("Send attempts"),
        help_text=_("Number of times we've attempted to send this email"),
        db_comment="Number of send attempts"
    )
    
    send_error = models.TextField(
        blank=True,
        verbose_name=_("Send error"),
        help_text=_("Error message if sending failed"),
        db_comment="Error message from failed send attempt"
    )
    
    in_reply_to = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("In reply to"),
        help_text=_("The Message-ID this email is replying to"),
        db_comment="Message-ID of email being replied to"
    )
    
    references = models.TextField(
        blank=True,
        verbose_name=_("References"),
        help_text=_("References header for email threading"),
        db_comment="References header for email threading"
    )
    
    # Custom manager
    objects = EmailManager()
    
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


class Attachment(TimestampMixin):
    """
    Model for storing email attachments.
    
    Represents files attached to email messages.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for attachment"
    )
    
    email = models.ForeignKey(
        Email,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name=_("Email"),
        help_text=_("The email this attachment belongs to"),
        db_comment="Reference to the email containing this attachment"
    )
    
    filename = models.CharField(
        max_length=255,
        verbose_name=_("Filename"),
        help_text=_("The original filename of the attachment"),
        db_comment="Original filename of the attachment"
    )
    
    content_type = models.CharField(
        max_length=255,
        default="application/octet-stream",
        verbose_name=_("Content type"),
        help_text=_("The MIME content type of the attachment"),
        db_comment="MIME content type of the attachment"
    )
    
    size = models.IntegerField(
        default=0,
        verbose_name=_("Size"),
        help_text=_("The size of the attachment in bytes"),
        db_comment="Size of the attachment in bytes"
    )
    
    content_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Content ID"),
        help_text=_("The Content-ID header for inline attachments"),
        db_comment="Content-ID header for inline attachments"
    )
    
    content_transfer_encoding = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Content transfer encoding"),
        help_text=_("The content transfer encoding used"),
        db_comment="Content transfer encoding method"
    )
    
    file_path = models.FileField(
        upload_to="attachments/%Y/%m/%d/",
        null=True,
        blank=True,
        verbose_name=_("File path"),
        help_text=_("The path to the stored attachment file"),
        db_comment="Path to the stored attachment file"
    )
    
    checksum = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name=_("Checksum"),
        help_text=_("SHA-256 checksum of the file content"),
        db_comment="SHA-256 checksum for integrity verification"
    )
    
    class Meta:
        db_table = "sage_attachment"
        verbose_name = _("Attachment")
        verbose_name_plural = _("Attachments")
        ordering = ["filename"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["filename"]),
            models.Index(fields=["content_type"]),
        ]
    
    def __str__(self):
        return f"{self.filename} ({self.content_type})"
    
    @property
    def is_image(self) -> bool:
        """Check if attachment is an image."""
        return self.content_type.startswith("image/")
    
    @property
    def is_text(self) -> bool:
        """Check if attachment is text-based."""
        return self.content_type.startswith("text/")
    
    @classmethod
    def from_sage_attachment(cls, sage_attachment: SageAttachment, email: Email) -> "Attachment":
        """Create Django Attachment instance from sage_imap Attachment."""
        import hashlib
        
        # Calculate checksum
        checksum = hashlib.sha256(sage_attachment.payload).hexdigest()
        
        return cls(
            email=email,
            filename=sage_attachment.filename,
            content_type=sage_attachment.content_type,
            size=len(sage_attachment.payload),
            content_id=sage_attachment.content_id,
            content_transfer_encoding=sage_attachment.content_transfer_encoding,
            checksum=checksum,
        )
    
    def to_sage_attachment(self) -> SageAttachment:
        """Convert Django Attachment instance to sage_imap Attachment."""
        # Read file content
        payload = b""
        if self.file_path:
            try:
                with open(self.file_path.path, 'rb') as f:
                    payload = f.read()
            except FileNotFoundError:
                pass
        
        return SageAttachment(
            filename=self.filename,
            content_type=self.content_type,
            payload=payload,
            id=str(self.id),
            content_id=self.content_id,
            content_transfer_encoding=self.content_transfer_encoding,
        )


class EmailFlag(TimestampMixin):
    """
    Model for storing custom email flags.
    
    Represents custom flags that can be applied to emails.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="Unique identifier for email flag"
    )
    
    email = models.ForeignKey(
        Email,
        on_delete=models.CASCADE,
        related_name="custom_flags",
        verbose_name=_("Email"),
        help_text=_("The email this flag applies to"),
        db_comment="Reference to the email with this flag"
    )
    
    flag_name = models.CharField(
        max_length=100,
        verbose_name=_("Flag name"),
        help_text=_("The name of the custom flag"),
        db_comment="Name of the custom flag"
    )
    
    flag_value = models.TextField(
        blank=True,
        verbose_name=_("Flag value"),
        help_text=_("The value of the custom flag"),
        db_comment="Value of the custom flag"
    )
    
    class Meta:
        db_table = "sage_email_flag"
        verbose_name = _("Email Flag")
        verbose_name_plural = _("Email Flags")
        unique_together = ["email", "flag_name"]
        ordering = ["flag_name"]
    
    def __str__(self):
        return f"{self.flag_name}: {self.flag_value}"
