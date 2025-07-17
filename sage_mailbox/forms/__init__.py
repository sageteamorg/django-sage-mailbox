"""
Forms package for sage_mailbox.

This package contains all Django forms for the sage_mailbox application.
Forms are organized by their functional responsibilities.
"""

from .base import BaseForm
from .server_forms import IMAPServerForm, SMTPServerForm
from .email_forms import EmailForm, EmailComposeForm

__all__ = [
    'BaseForm',
    'IMAPServerForm',
    'SMTPServerForm',
    'EmailForm',
    'EmailComposeForm',
] 