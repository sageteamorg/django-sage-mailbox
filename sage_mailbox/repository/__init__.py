"""
Repository layer for sage_mailbox.

This module provides a repository pattern implementation for managing
email-related database operations with clean separation of concerns.
"""

from .manager import EmailManager, MailboxManager
from .queryset import EmailQuerySet, MailboxQuerySet

__all__ = [
    'EmailManager',
    'MailboxManager', 
    'EmailQuerySet',
    'MailboxQuerySet',
] 