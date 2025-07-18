"""
Attachment model for sage_mailbox.

This module contains the Attachment model for storing email attachments.
Attachments represent files that are attached to email messages.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from sage_imap.models.email import Attachment as SageAttachment

from .mixins import TimestampMixin
from .email import Email


def attachment_upload_to(instance, filename):
    """
    Generate upload path for attachments with better folder structure.
    
    Path format: attachments/{server_host}/{mailbox_name}/{year}/{month}/{day}/{filename}
    This provides better organization by grouping attachments by server and mailbox.
    """
    import os
    from datetime import datetime
    
    # Get current date
    now = datetime.now()
    
    # Get server and mailbox info
    server_host = instance.email.mailbox.server.host
    mailbox_name = instance.email.mailbox.name
    
    # Clean server host and mailbox name for filesystem
    server_host = server_host.replace('.', '_').replace(':', '_')
    mailbox_name = mailbox_name.replace('/', '_').replace('\\', '_')
    
    # Build path
    path = os.path.join(
        'attachments',
        server_host,
        mailbox_name,
        now.strftime('%Y'),
        now.strftime('%m'),
        now.strftime('%d'),
        filename
    )
    
    return path


class Attachment(TimestampMixin):
    """
    File attachment associated with an email message.
    
    This model represents files that are attached to email messages.
    Attachments can be documents, images, or any other type of file.
    The system handles file storage, integrity verification, and type detection.
    
    Common attachment types:
    - Documents: PDF, Word, Excel, PowerPoint files
    - Images: JPG, PNG, GIF, etc.
    - Archives: ZIP, RAR, TAR files
    - Text files: TXT, CSV, etc.
    
    Each attachment belongs to a specific email and includes metadata
    about the file type, size, and content.
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
        help_text=_("The email message that contains this attachment"),
        db_comment="Reference to the email containing this attachment"
    )
    
    filename = models.CharField(
        max_length=255,
        verbose_name=_("Filename"),
        help_text=_("The original name of the attached file"),
        db_comment="Original filename of the attachment"
    )
    
    content_type = models.CharField(
        max_length=255,
        default="application/octet-stream",
        verbose_name=_("Content type"),
        help_text=_("The file type (e.g., 'image/jpeg', 'application/pdf')"),
        db_comment="MIME content type of the attachment"
    )
    
    size = models.IntegerField(
        default=0,
        verbose_name=_("Size"),
        help_text=_("Size of the attachment file in bytes"),
        db_comment="Size of the attachment in bytes"
    )
    
    content_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Content ID"),
        help_text=_("Unique identifier for inline attachments (used in HTML emails)"),
        db_comment="Content-ID header for inline attachments"
    )
    
    content_transfer_encoding = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Content transfer encoding"),
        help_text=_("How the file data was encoded for email transmission"),
        db_comment="Content transfer encoding method"
    )
    
    file_path = models.FileField(
        upload_to=attachment_upload_to,
        null=True,
        blank=True,
        verbose_name=_("File path"),
        help_text=_("Location where the attachment file is stored on disk"),
        db_comment="Path to the stored attachment file"
    )
    
    checksum = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name=_("Checksum"),
        help_text=_("Digital fingerprint to verify file integrity"),
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