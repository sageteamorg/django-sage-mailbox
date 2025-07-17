"""
Models for sage_mailbox.

This package contains all Django models for the sage_mailbox application.
Models are organized by their domain responsibilities.
"""

from .mixins import TimestampMixin
from .server import IMAPServer, SMTPServer
from .template import EmailTemplate
from .mailbox import Mailbox
from .email import Email
from .attachment import Attachment
from .flag import EmailFlag
from .proxy_models import (
    InboxEmail, SentEmail, DraftEmail, TrashEmail, SpamEmail,
    ImportantEmail, UnreadEmail, FlaggedEmail, AttachmentEmail,
    RecentEmail, LargeEmail, InboxMailbox, SentMailbox,
    DraftMailbox, TrashMailbox, SpamMailbox, CustomFolderMailbox
)

__all__ = [
    'TimestampMixin',
    'IMAPServer',
    'SMTPServer',
    'EmailTemplate',
    'Mailbox',
    'Email',
    'Attachment',
    'EmailFlag',
    'InboxEmail',
    'SentEmail',
    'DraftEmail',
    'TrashEmail',
    'SpamEmail',
    'ImportantEmail',
    'UnreadEmail',
    'FlaggedEmail',
    'AttachmentEmail',
    'RecentEmail',
    'LargeEmail',
    'InboxMailbox',
    'SentMailbox',
    'DraftMailbox',
    'TrashMailbox',
    'SpamMailbox',
    'CustomFolderMailbox',
] 