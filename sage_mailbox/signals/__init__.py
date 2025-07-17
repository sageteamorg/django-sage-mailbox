"""
Signals package for sage_mailbox.

This package provides signal handlers for email operations,
synchronization events, and model lifecycle events.
"""

# Import all signal handlers to ensure they are registered
from .email_signals import *
from .sync_signals import *
from .attachment_signals import *

__all__ = [
    'handle_email_created',
    'handle_email_updated',
    'handle_email_deleted',
    'handle_sync_started',
    'handle_sync_completed',
    'handle_sync_failed',
    'handle_attachment_created',
    'handle_attachment_deleted',
] 