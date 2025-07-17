"""
Mailbox model for sage_mailbox.

This module contains the Mailbox model for storing IMAP mailbox/folder information.
Mailboxes represent individual folders within an IMAP server.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from .mixins import TimestampMixin
from .server import IMAPServer
from ..repository.manager import MailboxManager


class Mailbox(TimestampMixin):
    """
    Email folder/mailbox within an IMAP server.
    
    This model represents individual mailboxes (folders) within an IMAP server.
    Mailboxes organize emails into different categories like Inbox, Sent, Drafts,
    or custom folders created by users.
    
    Each mailbox belongs to a specific IMAP server and can have a hierarchical
    structure with parent and child folders. The system tracks synchronization
    status and message counts for each mailbox.
    
    Common mailbox types:
    - INBOX: Incoming emails
    - Sent: Sent emails
    - Drafts: Draft emails
    - Trash: Deleted emails
    - Spam: Spam emails
    - Custom folders: User-created folders
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
        help_text=_("The email server that contains this mailbox"),
        db_comment="Reference to the IMAP server"
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name=_("Mailbox name"),
        help_text=_("The actual folder name on the email server (e.g., 'INBOX', 'Sent')"),
        db_comment="Name of the mailbox on the IMAP server"
    )
    
    display_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Display name"),
        help_text=_("A friendly name to show users instead of the technical folder name"),
        db_comment="Human-readable display name"
    )
    
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Default mailbox"),
        help_text=_("Check if this is a standard system folder (like Inbox, Sent, Drafts)"),
        db_comment="Whether this is a default system mailbox"
    )
    
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Parent mailbox"),
        help_text=_("The parent folder if this is a sub-folder (leave empty for top-level folders)"),
        db_comment="Parent mailbox for nested folder structure"
    )
    
    delimiter = models.CharField(
        max_length=5,
        default="/",
        verbose_name=_("Delimiter"),
        help_text=_("The character used to separate folder levels (usually '/' or '.')"),
        db_comment="Delimiter character for folder hierarchy"
    )
    
    uidvalidity = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("UID validity"),
        help_text=_("Technical value from the email server for tracking message uniqueness"),
        db_comment="UIDVALIDITY value from IMAP server"
    )
    
    uidnext = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_("UID next"),
        help_text=_("Technical value from the email server for the next message ID"),
        db_comment="UIDNEXT value from IMAP server"
    )
    
    message_count = models.IntegerField(
        default=0,
        verbose_name=_("Message count"),
        help_text=_("Total number of emails in this folder"),
        db_comment="Total number of messages in mailbox"
    )
    
    unseen_count = models.IntegerField(
        default=0,
        verbose_name=_("Unseen count"),
        help_text=_("Number of unread emails in this folder"),
        db_comment="Number of unseen messages in mailbox"
    )
    
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last sync"),
        help_text=_("When this folder was last synchronized with the email server"),
        db_comment="Timestamp of last synchronization"
    )
    
    objects: MailboxManager = MailboxManager()
    
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